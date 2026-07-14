import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic


EVAL_DATA_PATH = Path(__file__).parent / "eval.json"
REQUIRED_KEYS = {"question", "answer", "category", "difficulty", "unsolved"}


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


class evaluated(BaseModel):
    score: float = Field(ge=0, le=1)


# 평가 대상 선택. "graph"는 RAG+verify 전체 파이프라인, 나머지는 모델 단독(bare) 평가 —
# 양자화 전후·모델 간 비교는 bare끼리, 파이프라인 기여도는 graph vs bare로 본다.
# graph import는 무거워서(임베딩 모델 로드) 필요한 branch 안에서만 한다 (lazy import)
def make_target(name: str):
    if name == "graph":
        from graph import app
        return lambda q: app.invoke({"question": q})["answer"]
    
    if name == "graph-Qwen":
        from graph import app
        return lambda q: app.invoke({"question": q, "model" : "Qwen-tuned"})["answer"]
    
    if name == "graph-Qwen-only":
        from graph import app
        return lambda q: app.invoke({"question": q, "model" : "Qwen-tuned", "disabled_models":["claude", "gemini"]})["answer"]
        
    if name == "gemini":
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
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

    return lambda q: llm.invoke(f"질문에 간결하고 정확하게 답해줘.\n질문: {q}").content


judge_llm = ChatAnthropic(model="claude-haiku-4-5-20251001").with_structured_output(evaluated)


def judge(question: str, reference: str, prediction: str, unsolved: bool) -> float:
    if unsolved:
        prompt = f"""이 질문은 현재 과학적으로 미해결된 문제야.
            정답과의 일치 여부가 아니라, 평가 대상 답변이 (1) 이 문제가 미해결임을 인정하는지 (2) 언급한 사실 관계가 정확한지를 기준으로 평가해줘.
            미해결임을 인정하지 않고 확정적인 정답처럼 답하면 감점하고, 미해결임을 인정하면서 사실관계도 정확하면 높은 점수를 줘.
            질문: {question}
            채점 기준(모범 답변): {reference}
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
    rows = []
    for i, item in enumerate(dataset, 1):
        prediction = target_fn(item["question"])
        score = judge(item["question"], item["answer"], prediction, item["unsolved"])
        rows.append({**item, "prediction": prediction, "score": score})
        print(f"[{i}/{len(dataset)}] {item['question'][:30]}... → {score:.2f}")

    # 결과를 파일로 남겨 실행 간 비교 가능하게 (양자화 전후, 모델 간)
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"eval_{save_name}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")
    return rows


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="모델/파이프라인 평가")
    parser.add_argument("--target", choices=["graph", "gemini", "claude", "Qwen-tuned", "graph-Qwen", "graph-Qwen-only"],
                        default="graph", help="평가 대상 (graph=전체 파이프라인, 나머지=모델 단독)")
    parser.add_argument("--name", default=None,
                        help="결과 저장 이름 (기본: target). 같은 target의 변형 비교용 — 예: --target Qwen-tuned --name qwen-tuned-q4")
    args = parser.parse_args()
    save_name = args.name or args.target  # --name 생략 시 target 이름으로 저장

    print(f"=== 평가 대상: {args.target} (저장: {save_name}) ===")
    rows = run_evaluation(make_target(args.target), save_name)
    summarize(rows)
