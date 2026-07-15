import argparse
import json
import os
import sys
from pathlib import Path

# graph.py 등은 저장소 루트에 있는데 이 파일은 evaluation/ 아래로 옮겨졌으므로,
# `from graph import app`이 되려면 루트를 sys.path에 직접 추가해야 한다
# (스크립트로 실행하면 자기 디렉토리만 sys.path에 잡히고 상위 디렉토리는 안 잡힘).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

# 쿼터/사용량 제한으로 중간에 멈출 수 있는 에러들 — models.py의 invoke_with_fallback과 같은 목록
# (graph 계열 target은 전부 소진되면 RuntimeError로 올라오므로 그것도 같이 잡는다)
from google.api_core.exceptions import ResourceExhausted, PermissionDenied  # PermissionDenied: 결제 계정 정지 등으로 403 뜰 때
from anthropic import RateLimitError
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from openai import APIConnectionError, BadRequestError, LengthFinishReasonError

QUOTA_ERRORS = (ResourceExhausted, PermissionDenied, RateLimitError, ChatGoogleGenerativeAIError,
                APIConnectionError, BadRequestError, LengthFinishReasonError, RuntimeError)


EVAL_DATA_PATH = Path(__file__).parent / "eval.json"
REQUIRED_KEYS = {"question", "answer", "category", "difficulty", "unsolved"}


# eval.json 스키마를 여기서 미리 검증한다 — 문항 하나하나 채점하다가 중간에
# 필수 키 누락으로 KeyError가 나면 그때까지의 진행이 애매해지니, 로드 시점에 한 번에 잡는다.
def load_eval_dataset(path: Path = EVAL_DATA_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        items = json.load(f)

    if not isinstance(items, list):
        raise ValueError(f"{path}: 최상위 요소는 리스트여야 합니다")

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{path}[{i}]: 각 항목은 객체여야 합니다")
        missing = REQUIRED_KEYS - item.keys()
        if missing:
            raise ValueError(
                f"{path}[{i}] (question={item.get('question')!r}): 필수 키 누락 {sorted(missing)}"
            )

    return items


# judge LLM의 structured output 스키마 — "숫자만 답해줘" 프롬프트를 던져도
# 자유 텍스트가 섞여 나올 수 있으니, 0~1 범위의 score 하나만 강제로 뽑아낸다.
class evaluated(BaseModel):
    score: float = Field(ge=0, le=1)


# target_fn은 전부 (prediction: str, meta: dict)를 반환한다.
# meta의 generated_by로 실제 어느 모델이 답했는지 결과 파일에 남겨, graph처럼 내부에서
# fallback이 조용히 다른 모델로 넘어갈 수 있는 target도 사후에 어느 모델이 얼마나 답했는지 확인 가능
def _graph_target(invoke_kwargs: dict):
    from graph import app
    def _run(q: str):
        result = app.invoke({"question": q, **invoke_kwargs})
        return result["answer"], {"generated_by": result.get("generated_by", "")}
    return _run


# 평가 대상 선택. "graph"는 RAG+verify 전체 파이프라인, 나머지는 모델 단독(bare) 평가 —
# 양자화 전후·모델 간 비교는 bare끼리, 파이프라인 기여도는 graph vs bare로 본다.
# graph import는 무거워서(임베딩 모델 로드) 필요한 branch 안에서만 한다 (lazy import, _graph_target 내부에서)
def make_target(name: str):
    if name == "graph":
        return _graph_target({})

    if name == "graph-Qwen":
        return _graph_target({"model": "Qwen-tuned"})

    if name == "graph-Qwen-only":
        return _graph_target({"model": "Qwen-tuned", "disabled_models": ["claude", "gemini"]})

    if name == "graph-gemini-only":
        # 파이프라인 안에서 fallback 없이 gemini만 순수하게 — claude로 새는 걸 막아서
        # "구조 개선이 gemini만으로도 점수를 올리는가"를 다른 모델 기여 없이 확인
        return _graph_target({"model": "gemini", "disabled_models": ["claude", "Qwen-tuned"]})
    
    if name == "graph-claude-only":
        return _graph_target({"model": "claude", "disabled_models": ["gemini", "Qwen-tuned"]})

    if name == "gemini":
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0) # 재현 위해
    elif name == "claude":
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
    elif name == "Qwen-tuned":
        # OpenAI 클라우드가 아니라 완전 로컬 — llama-server(llama.cpp)가 GGUF를 로드하고
        # localhost에 OpenAI '호환 형식'의 HTTP 인터페이스를 열 뿐이다. 데이터는 밖으로 안 나감.
        # 실행: llama-server -m ./qwen-tuned.gguf --port 8080
        # Ollama라면: LOCAL_MODEL_URL=http://localhost:11434/v1 LOCAL_MODEL_NAME=<태그>
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            base_url=os.getenv("LOCAL_MODEL_URL", "http://localhost:8080/v1"),
            api_key="not-needed",  # 로컬 서버는 키 검사 안 함 (필드가 필수라 더미값)
            model=os.getenv("LOCAL_MODEL_NAME", "qwen-tuned"),
            temperature=0,
        )
    else:
        raise ValueError(f"알 수 없는 target: {name}")

    return lambda q: (llm.invoke(f"질문에 간결하고 정확하게 답해줘.\n질문: {q}").content, {"generated_by": name})


# judge는 항상 claude-haiku로 고정 — 평가 대상(gemini/claude/Qwen-tuned)과 겹치면
# 자기 자신이 낸 답을 자기가 채점하는 경우가 생길 수 있긴 함.
judge_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0).with_structured_output(evaluated)


# unsolved(미해결 문제)는 "정답과 얼마나 같은가"가 아니라 "모른다는 걸 인정하는가"가
# 채점 기준이 되어야 해서, 두 갈래로 프롬프트 자체를 다르게 구성한다.
def judge(question: str, reference: str, prediction: str, unsolved: bool) -> float:
    if unsolved:
        prompt = f"""이 질문은 현재 과학적으로 미해결된 문제야.
            정답과의 일치 여부가 아니라, 평가 대상 답변이 (1) 이 문제가 미해결임을 인정하는지 (2) 언급한 사실 관계가 정확한지를 기준으로 평가해줘.
            미해결임을 인정하지 않고 확정적인 정답처럼 답하면 감점하고, 미해결임을 인정하면서 사실관계도 정확하면 높은 점수를 줘.
            질문: {question}
            참고 답변: {reference}
            평가 대상 답변: {prediction}
            0.0(미해결 인정 없이 확정적으로 단언)~1.0(미해결 인정 + 사실관계 정확) 사이 숫자만 답해줘."""
    else:
        prompt = f"""질문에 대한 답변이 참고 답변과 의미적으로 일치하는지 평가해줘.
            질문: {question}
            참고 답변: {reference}
            평가 대상 답변: {prediction}
            0.0(완전 틀림)~1.0(완전 정확) 사이 숫자만 답해줘."""

    return judge_llm.invoke(prompt).score


def run_evaluation(target_fn, save_name: str) -> list[dict]:
    dataset = load_eval_dataset()

    # 결과를 파일로 남겨 실행 간 비교 가능하게 (양자화 전후, 모델 간)
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"eval_{save_name}.json"

    # 이어서 하기: 같은 이름으로 저장된 결과가 이미 있으면 끝난 문항은 건너뛰고 이어감
    # (question 텍스트로 매칭 — eval.json 순서가 바뀌어도 안전)
    rows: list[dict] = []
    if out_path.exists():
        with out_path.open(encoding="utf-8") as f:
            rows = json.load(f)
        print(f"이어서 진행: 기존 결과 {len(rows)}/{len(dataset)}문항 발견 ({out_path.name})")

    done_questions = {r["question"] for r in rows}

    def save() -> None:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    # 핵심 파트
    for i, item in enumerate(dataset, 1):
        if item["question"] in done_questions:
            continue #건너뛰기
        try:
            prediction, meta = target_fn(item["question"])
            score = judge(item["question"], item["answer"], prediction, item["unsolved"])
        except QUOTA_ERRORS as e:
            print(f"\n[{i}/{len(dataset)}]에서 중단: {type(e).__name__}: {e}")
            print(f"지금까지 {len(rows)}/{len(dataset)}문항 저장함 → {out_path}")
            print("쿼터가 복구된 후 같은 명령어로 다시 실행하면 이어서 진행됨.")
            save()
            return rows

        rows.append({**item, "prediction": prediction, **meta, "score": score})
        done_questions.add(item["question"])
        print(f"[{i}/{len(dataset)}] {item['question'][:30]}... → {score:.2f}")
        save()  # 문항마다 저장 — 예상 못한 다른 크래시가 나도 여기까지는 보존됨

    print(f"\n결과 저장: {out_path} (완료 {len(rows)}/{len(dataset)}문항)")
    return rows


# 전체/일반/미해결/카테고리별 평균 점수를 콘솔에 출력만 한다 (반환값 없음) —
# run_evaluation이 만든 rows를 다른 방식으로 더 들여다보고 싶으면 여기 대신 results/*.json을 직접 열어보면 됨.
def summarize(rows: list[dict]) -> None:
    def avg(scores: list[float]) -> float:
        return sum(scores) / len(scores) if scores else float("nan")

    solved = [r for r in rows if not r["unsolved"]]
    unsolved = [r for r in rows if r["unsolved"]]

    print("\n=== 평가 요약 ===")
    print(f"전체: 평균 {avg([r['score'] for r in rows]):.3f} (n={len(rows)})")
    print(f"일반 문항: 평균 {avg([r['score'] for r in solved]):.3f} (n={len(solved)})")
    print(f"미해결 문항(인정+사실정확성): 평균 {avg([r['score'] for r in unsolved]):.3f} (n={len(unsolved)})")

    print("\n카테고리별 평균:")
    for category in sorted({r["category"] for r in rows}):
        cat_rows = [r for r in rows if r["category"] == category]
        print(f"  {category}: 평균 {avg([r['score'] for r in cat_rows]):.3f} (n={len(cat_rows)})")


if __name__ == "__main__": # 직접 실행할때만 동작
    parser = argparse.ArgumentParser(description="모델/파이프라인 평가")
    parser.add_argument("--target", choices=["graph", "gemini", "claude", "Qwen-tuned", "graph-Qwen", "graph-Qwen-only", "graph-gemini-only","graph-claude-only"],
                        default="graph", help="평가 대상 (graph=전체 파이프라인, 나머지=모델 단독)")
    parser.add_argument("--name", default=None,
                        help="결과 저장 이름 (기본: target). 같은 target의 변형 비교용 — 예: --target Qwen-tuned --name qwen-tuned-q4")
    args = parser.parse_args()
    save_name = args.name or args.target  # --name 생략 시 target 이름으로 저장

    print(f"=== 평가 대상: {args.target} (저장: {save_name}) ===")
    rows = run_evaluation(make_target(args.target), save_name)

    dataset_len = len(load_eval_dataset())
    if len(rows) < dataset_len:
        print(f"\n⚠ {len(rows)}/{dataset_len}문항만 완료됨 — 아래 요약은 미완성 결과 기준. 같은 명령어로 다시 실행하면 이어서 진행됨.")
    summarize(rows)
