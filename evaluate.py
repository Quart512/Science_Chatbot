import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

from graph import app

EVAL_DATA_PATH = Path(__file__).parent / "docs" / "eval.json"
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


def graph_fn(inputs):
    return {"answer": app.invoke({"question": inputs["question"]})["answer"]}


judge_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash").with_structured_output(evaluated)


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


def run_evaluation() -> list[dict]:
    dataset = load_eval_dataset()
    rows = []
    for item in dataset:
        prediction = graph_fn({"question": item["question"]})["answer"]
        score = judge(item["question"], item["answer"], prediction, item["unsolved"])
        rows.append({**item, "prediction": prediction, "score": score})
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
    rows = run_evaluation()
    summarize(rows)
