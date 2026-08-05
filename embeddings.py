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
"""
import numpy as np
import onnxruntime as ort
from huggingface_hub import snapshot_download
from langchain_core.embeddings import Embeddings
from tokenizers import Tokenizer

MODEL_ID = "BAAI/bge-m3"
MAX_SEQ_LENGTH = 8192  # bge-m3의 sentence_bert_config.json 값
PAD_TOKEN_ID = 1       # XLM-RoBERTa의 <pad>. attention_mask로 가려지므로 결과에 영향 없음

# sentence-transformers가 내부적으로 해주던 배치 처리를 직접 해야 한다 — 안 하면
# ingest.py가 파인만 청크 수천 개를 한 번에 넘길 때 거대한 텐서 하나를 만들려다 죽는다.
BATCH_SIZE = 16


class BGEM3OnnxEmbeddings(Embeddings):
    """langchain의 Embeddings 계약(embed_documents / embed_query)만 구현한 얇은 어댑터.

    벡터스토어 쪽 코드는 이 클래스가 무엇으로 돌아가는지 몰라도 되게 격리한다
    (pdf_parse.py·arxiv_api.py와 같은 "교체 가능하게 어댑터 뒤에" 원칙) — 나중에
    양자화 모델이나 다른 런타임으로 갈아탈 때 바꿀 파일이 여기 하나로 유지된다.
    """

    def __init__(self) -> None:
        # allow_patterns로 onnx/ 폴더만 받는다 — 안 그러면 pytorch_model.bin(2.1GB)까지
        # 같이 받아 쓰지도 않을 파일로 용량이 두 배가 된다.
        model_dir = snapshot_download(MODEL_ID, allow_patterns=["onnx/*"])
        onnx_dir = f"{model_dir}/onnx"

        self._tokenizer = Tokenizer.from_file(f"{onnx_dir}/tokenizer.json")
        self._tokenizer.enable_truncation(max_length=MAX_SEQ_LENGTH)

        self._session = ort.InferenceSession(
            f"{onnx_dir}/model.onnx", providers=["CPUExecutionProvider"]
        )
        self._input_names = {i.name for i in self._session.get_inputs()}
        # 출력이 [token_embeddings, sentence_embedding] 순 — 이름으로 찾는다.
        # 인덱스로 박으면 익스포트가 바뀌었을 때 조용히 엉뚱한 값을 쓰게 된다.
        self._sentence_output_index = next(
            i for i, o in enumerate(self._session.get_outputs())
            if o.name == "sentence_embedding"
        )

    def _encode_batch(self, texts: list[str]) -> np.ndarray:
        encodings = [self._tokenizer.encode(t) for t in texts]
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
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.zeros_like(input_ids)

        outputs = self._session.run(None, feed)
        return outputs[self._sentence_output_index]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = self._encode_batch(texts[start : start + BATCH_SIZE])
            vectors.extend(batch.tolist())
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._encode_batch([text])[0].tolist()
