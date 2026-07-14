"""docs/eval.json으로부터 docs/eval.md(카테고리별 표)를 생성한다."""
import json
from pathlib import Path

EVAL_JSON = Path(__file__).parent / "eval.json"
EVAL_MD = Path(__file__).parent / "eval.md"

CATEGORY_LABELS = {
    "atomic": "원자 / 물질",
    "mechanics": "고전역학",
    "electromagnetism": "전자기학",
    "thermodynamics": "열역학 / 통계역학",
    "relativity": "상대성이론",
    "quantum": "양자역학",
    "open_problem": "미해결 문제",
}


def render(items: list[dict]) -> str:
    by_category: dict[str, list[dict]] = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item)

    lines = ["# 평가 데이터셋 (eval.json)", ""]
    lines.append(f"총 {len(items)}문항, 카테고리 {len(by_category)}개")
    lines.append("")

    for category, rows in by_category.items():
        label = CATEGORY_LABELS.get(category, category)
        lines.append(f"## {label} (`{category}`)")
        lines.append("")
        lines.append("| 난이도 | 미해결 | 질문 | 답변 |")
        lines.append("|---|---|---|---|")
        for row in rows:
            unsolved_mark = "O" if row["unsolved"] else ""
            question = row["question"].replace("|", "\\|")
            answer = row["answer"].replace("|", "\\|")
            lines.append(f"| {row['difficulty']} | {unsolved_mark} | {question} | {answer} |")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    items = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
    EVAL_MD.write_text(render(items), encoding="utf-8")
    print(f"generated {EVAL_MD} from {len(items)} items")
