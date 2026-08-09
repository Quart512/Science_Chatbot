"""BAAI/bge-m3 임베딩 — onnxruntime 백엔드.

원래는 `HuggingFaceEmbeddings(model_name="BAAI/bge-m3")` 한 줄이었다(retrieval.py).
그 경로가 sentence-transformers를 거쳐 torch를 끌어왔고, torch 하나가 site-packages
519MB에 딸린 scipy·transformers·sympy·sklearn까지 합쳐 **731MB**를 차지했다 —
로컬 배포판에서 사용자가 직접 내려받는 용량이라 그대로 두기 어려웠다(CLAUDE.md §5).

**왜 이 방향이 안전한가 (08-05 실측, RoadMap 설계 노트 "torch 제거 가능성 조사" 참고)**
- bge-m3 저장소에 **공식 ONNX 익스포트**가 있다(`onnx/model.onnx` + `model.onnx_data`).
- 그 익스포트의 `sentence_embedding` 출력은 **CLS 풀링과 L2 정규화까지 끝난 값**이다
  (modules.json이 정의한 Transformer→Pooling(CLS)→Normalize 3단계가 그래프에 포함됨).
  그래서 여기서 풀링·정규화를 직접 구현하지 않는다 — 구현하면 그만큼 틀릴 여지가 생긴다.
- torch 경로로 뽑은 벡터와 비교해 **코사인 유사도 최소 0.999999934, 최대 절대 오차
  3.24e-07**. 문장 간 유사도 행렬 차이도 1.92e-07이라 검색 순위가 보존된다 —
  즉 **기존 chroma_db를 재색인하지 않아도 된다**(CLAUDE.md §5의 "ingest.py와 검색
  경로가 반드시 같은 모델" 제약을 만족).
- 새로 추가되는 의존성이 **없다**: onnxruntime은 chromadb·pymupdf-layout이,
  tokenizers는 chromadb가 이미 끌어온다.

**주의**: 모델 다운로드 용량은 안 줄어든다(ONNX 가중치 2161.8MB vs pytorch_model.bin
2165.9MB로 사실상 동일). 이 교체의 이득은 "런타임 731MB 제거"지 "첫 실행 다운로드
완화"가 아니다. 후자까지 노리려면 int8 양자화 ONNX가 필요한데 그건 가중치가 실제로
달라져 재색인을 동반하므로 별개 판단이다.

**지연 로딩 (08-09)** — 원래는 `__init__`에서 곧바로 `snapshot_download`를 불렀고,
retrieval.py가 모듈 최상단에서 이 클래스를 인스턴스화하는 탓에 **`import retrieval`이
2.1GB 다운로드를 끝낼 때까지 블로킹**됐다. main.py가 retrieval을 import하므로 FastAPI가
뜨기도 전의 일이라, 사용자는 앱을 더블클릭한 뒤 몇 분간 창도 진행률도 없는 상태를 봤다.
게다가 run.sh의 헬스 폴링이 360초에서 포기해서, 회선이 느리면 **앱이 정상인데도
"서버가 응답하지 않습니다"로 실패**했다(08-09 실사용자 환경에서 원인 확인).

그래서 무거운 준비(다운로드 + ONNX 세션 생성)를 모듈 수준 `load()`로 빼고 실제 임베딩이
필요한 순간까지 미룬다. retrieval.py는 한 글자도 안 바뀐다 — 벡터스토어 쪽이 이 클래스의
내부를 몰라도 되게 어댑터 뒤에 격리해둔 설계가 여기서 값을 한다. main.py는 lifespan에서
`prefetch()`를 배경 스레드로 던져 서버 기동과 다운로드를 동시에 진행시키고, 프론트는
`get_status()`가 실린 엔드포인트를 폴링해 진행률을 보여준다.
"""
import threading

import numpy as np
import onnxruntime as ort
from huggingface_hub import snapshot_download
from huggingface_hub.utils import tqdm as hf_tqdm
from langchain_core.embeddings import Embeddings
from tokenizers import Tokenizer

MODEL_ID = "BAAI/bge-m3"
MAX_SEQ_LENGTH = 8192  # bge-m3의 sentence_bert_config.json 값
PAD_TOKEN_ID = 1       # XLM-RoBERTa의 <pad>. attention_mask로 가려지므로 결과에 영향 없음

# sentence-transformers가 내부적으로 해주던 배치 처리를 직접 해야 한다 — 안 하면
# ingest.py가 파인만 청크 수천 개를 한 번에 넘길 때 거대한 텐서 하나를 만들려다 죽는다.
BATCH_SIZE = 16


# ── 지연 로딩 + 진행률 ────────────────────────────────────────────────────────
# 상태 값. "idle"은 아직 아무도 임베딩을 요구하지 않은 상태고, prefetch()가 돌면 곧바로
# "downloading"으로 넘어간다. 이미 캐시에 있으면 다운로드가 즉시 끝나 "loading"만 잠깐
# 보인다(ONNX 세션이 2.1GB를 메모리로 올리는 시간).
_status: dict = {"state": "idle", "downloaded_bytes": 0, "total_bytes": 0, "error": None}
_status_lock = threading.Lock()  # 다운로드 스레드가 쓰고 요청 스레드가 읽으므로 필요
_load_lock = threading.Lock()    # 무거운 준비를 정확히 한 번만
_model = None                    # 준비 완료된 (tokenizer, session, ...) 묶음


def get_status() -> dict:
    """프론트 진행률 표시용 스냅샷. 호출부가 들고 있는 동안 배경 스레드가 값을 바꾸면
    혼란스러우니 사본을 준다."""
    with _status_lock:
        return dict(_status)


def _set_status(**changes) -> None:
    with _status_lock:
        _status.update(changes)


def _add_downloaded(delta: int) -> None:
    with _status_lock:
        _status["downloaded_bytes"] += delta


class _ProgressTqdm(hf_tqdm):
    """snapshot_download의 진행률을 _status로 흘려보내는 tqdm 서브클래스.

    huggingface_hub는 `tqdm_class`를 **두 번** 인스턴스화한다 — 파일 개수 바 하나,
    바이트 집계 바 하나(_snapshot_download.py의 `bytes_progress`). 둘을 구분하는
    표식은 `unit="B"`뿐이라 그걸로 가른다.

    hf의 tqdm을 상속하는 게 중요하다. `_create_progress_bar`가 "hf tqdm의 서브클래스인가"를
    보고 `disable`(TTY 자동 감지)과 `name`을 넘길지 정하는데, 번들 실행에선 stderr가
    logs/server.log 파일이라 자동으로 바 출력이 꺼진다 — 로그가 진행률 갱신으로
    도배되지 않는다. 대신 **disable=True면 tqdm이 self.unit을 아예 설정하지 않고
    __init__을 일찍 반환**하므로, 판별 플래그는 super() 호출 전에 직접 챙겨야 한다.
    같은 이유로 self.n도 안 늘어나서, 진행량은 tqdm 내부값을 읽지 않고 델타로 누적한다.

    huggingface_hub가 이 배선을 바꾸면 진행률만 0에 머물고 상태 전이는 그대로 동작한다
    (퍼센트 대신 무한 스피너로 자연 열화 — 다운로드 자체가 깨지지는 않는다).
    """

    def __init__(self, *args, **kwargs):
        self._tracks_bytes = kwargs.get("unit") == "B"
        super().__init__(*args, **kwargs)

    def update(self, n=1):
        if self._tracks_bytes and n:
            _add_downloaded(n)
        return super().update(n)

    def refresh(self, *args, **kwargs):
        # 총량은 파일 메타데이터가 도착할 때마다 커진다(0에서 시작해 누적) — 그래서
        # 총량 갱신은 update()가 아니라 refresh() 시점에 읽는다.
        if self._tracks_bytes:
            _set_status(total_bytes=self.total or 0)
        return super().refresh(*args, **kwargs)


def load():
    """모델을 준비하고 (tokenizer, session, input_names, sentence_output_index)를 돌려준다.

    여러 요청이 동시에 첫 임베딩을 시도해도 다운로드·세션 생성이 한 번만 일어나게 락으로
    감싼다. 이미 준비됐으면 락도 안 잡고 즉시 반환한다(임베딩 호출마다 락을 잡으면
    ingest 같은 대량 경로에서 불필요한 직렬화가 생긴다).
    """
    global _model
    if _model is not None:
        return _model

    with _load_lock:
        if _model is not None:  # 락을 기다리는 사이 다른 스레드가 끝냈을 수 있다
            return _model
        try:
            _set_status(state="downloading", error=None)
            # allow_patterns로 onnx/ 폴더만 받는다 — 안 그러면 pytorch_model.bin(2.1GB)까지
            # 같이 받아 쓰지도 않을 파일로 용량이 두 배가 된다.
            model_dir = snapshot_download(
                MODEL_ID, allow_patterns=["onnx/*"], tqdm_class=_ProgressTqdm
            )
            onnx_dir = f"{model_dir}/onnx"

            _set_status(state="loading")
            tokenizer = Tokenizer.from_file(f"{onnx_dir}/tokenizer.json")
            tokenizer.enable_truncation(max_length=MAX_SEQ_LENGTH)

            session = ort.InferenceSession(
                f"{onnx_dir}/model.onnx", providers=["CPUExecutionProvider"]
            )
            input_names = {i.name for i in session.get_inputs()}
            # 출력이 [token_embeddings, sentence_embedding] 순 — 이름으로 찾는다.
            # 인덱스로 박으면 익스포트가 바뀌었을 때 조용히 엉뚱한 값을 쓰게 된다.
            sentence_output_index = next(
                i for i, o in enumerate(session.get_outputs())
                if o.name == "sentence_embedding"
            )
        except Exception as e:
            # 실패를 상태에 남겨 화면이 "준비 중"에 영영 머물지 않게 한다(§3 "조용히
            # 자르지 말고 정직하게 실패"). 다음 호출은 처음부터 다시 시도한다 —
            # 네트워크 단절이 원인인 경우가 대부분이라 재시도가 실제로 복구된다.
            _set_status(state="failed", error=f"{type(e).__name__}: {e}")
            raise

        _model = (tokenizer, session, input_names, sentence_output_index)
        _set_status(state="ready")
        return _model


def prefetch() -> None:
    """서버 기동 직후 배경 스레드에서 부르는 진입점. 예외를 삼키는 게 load()와 다른
    점이다 — 배경 준비가 실패했다고 서버가 죽으면 안 되고, 실패 사실은 이미 _status에
    남아 화면으로 전달된다."""
    try:
        load()
    except Exception:
        pass


class BGEM3OnnxEmbeddings(Embeddings):
    """langchain의 Embeddings 계약(embed_documents / embed_query)만 구현한 얇은 어댑터.

    벡터스토어 쪽 코드는 이 클래스가 무엇으로 돌아가는지 몰라도 되게 격리한다
    (pdf_parse.py·arxiv_api.py와 같은 "교체 가능하게 어댑터 뒤에" 원칙) — 나중에
    양자화 모델이나 다른 런타임으로 갈아탈 때 바꿀 파일이 여기 하나로 유지된다.
    """

    # __init__을 안 둔다 — 생성은 공짜여야 한다. retrieval.py가 모듈 최상단에서 이걸
    # 만들기 때문에, 여기서 무거운 일을 하면 그게 곧 `import retrieval`의 비용이 된다
    # (모듈 docstring "지연 로딩" 참고).

    def _encode_batch(self, texts: list[str]) -> np.ndarray:
        tokenizer, session, input_names, sentence_output_index = load()

        encodings = [tokenizer.encode(t) for t in texts]
        # 패딩은 "이 배치 안의 최대 길이"까지만 — 전체 최대(8192)로 맞추면 짧은 청크
        # 수천 개를 처리할 때 대부분이 pad인 행렬을 만들어 메모리를 헛되이 쓴다.
        max_len = max(len(e.ids) for e in encodings)

        input_ids = np.full((len(encodings), max_len), PAD_TOKEN_ID, dtype=np.int64)
        attention_mask = np.zeros((len(encodings), max_len), dtype=np.int64)
        for row, encoding in enumerate(encodings):
            input_ids[row, : len(encoding.ids)] = encoding.ids
            attention_mask[row, : len(encoding.ids)] = 1

        feed = {"input_ids": input_ids, "attention_mask": attention_mask}
        # XLM-R은 token_type_ids를 안 쓰지만 익스포트에 따라 입력에 남아있을 수 있다.
        if "token_type_ids" in input_names:
            feed["token_type_ids"] = np.zeros_like(input_ids)

        outputs = session.run(None, feed)
        return outputs[sentence_output_index]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = self._encode_batch(texts[start : start + BATCH_SIZE])
            vectors.extend(batch.tolist())
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._encode_batch([text])[0].tolist()
