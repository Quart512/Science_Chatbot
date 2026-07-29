# -*- coding: utf-8 -*-
"""docs/architecture.png 생성 스크립트 — 표면/능력/데이터 3층 아키텍처 다이어그램.

설계가 바뀌면 이 파일의 box(...) 정의만 고치고 다시 실행한다:
    uv run docs/draw_architecture.py

한글 폰트가 필요하다. FONT_DIR을 환경에 맞게 바꿀 것
(macOS: /System/Library/Fonts/AppleSDGothicNeo.ttc, Linux: Noto Sans CJK KR).
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.font_manager import FontProperties

# 폰트 — 없으면 첫 번째 후보로 fallback (환경에 맞게 수정)
FONT_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc",
     "/System/Library/Fonts/AppleSDGothicNeo.ttc"),
]
for reg, bold in FONT_CANDIDATES:
    if os.path.exists(reg):
        F_REG, F_BOLD = FontProperties(fname=reg), FontProperties(fname=bold)
        break
else:
    raise SystemExit("한글 폰트를 찾지 못했다 — FONT_CANDIDATES에 경로를 추가할 것")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture.png")

C_SURF_BAND = "#EEF3FA"; C_SURF_EDGE = "#3B6EA5"
C_CAP_BAND  = "#F3F0FA"; C_CAP_EDGE  = "#6B4FA0"
C_DATA_BAND = "#EFF7EF"; C_DATA_EDGE = "#3E7A4C"
C_HUB       = "#FBEEDB"; C_HUB_EDGE  = "#C07A2D"
C_TEXT = "#1F2430"; C_SUB = "#5A6270"; C_DASH = "#8A5A9E"; C_DATA_ARROW = "#5B8A67"

fig, ax = plt.subplots(figsize=(16, 10.8), dpi=150)
ax.set_xlim(0, 160); ax.set_ylim(0, 108)
ax.axis("off")
fig.patch.set_facecolor("white")


def band(x, y, w, h, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc=fc, ec="none", zorder=1))


def box(x0, x1, y0, y1, title, sub=None, ec=C_CAP_EDGE, fc="white", ts=10, ss=7.5,
        done=False):
    # done=True면 테두리를 굵게 — "이미 구현된 것"과 "계획"을 한눈에 구분하기 위한 표시.
    # 색을 따로 쓰지 않는 이유: 층(표면/능력/데이터)을 이미 색으로 구분하고 있어서
    # 색을 하나 더 얹으면 두 축이 섞여 읽기 어려워진다.
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                boxstyle="round,pad=0.25,rounding_size=0.8",
                                fc=fc, ec=ec, lw=3.0 if done else 1.6, zorder=3))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if sub:
        ax.text(cx, cy + 1.5, title, ha="center", va="center", fontsize=ts,
                fontproperties=F_BOLD, color=C_TEXT, zorder=4)
        ax.text(cx, cy - 2.2, sub, ha="center", va="center", fontsize=ss,
                fontproperties=F_REG, color=C_SUB, zorder=4)
    else:
        ax.text(cx, cy, title, ha="center", va="center", fontsize=ts,
                fontproperties=F_BOLD, color=C_TEXT, zorder=4)


def arrow(p0, p1, color="#44506B", lw=1.8, rad=0.0, ls="solid"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14,
                                 color=color, lw=lw, linestyle=ls, zorder=2,
                                 connectionstyle=f"arc3,rad={rad}"))


# ── 제목
ax.text(80, 105.8, "Science Chatbot — 목표 아키텍처 (표면 / 능력 / 데이터 3층)",
        ha="center", va="center", fontsize=15, fontproperties=F_BOLD, color=C_TEXT)
ax.text(80, 102.2, "굵은 테두리 = 구현 완료 · 얇은 테두리 = 계획",
        ha="center", va="center", fontsize=8.5, fontproperties=F_REG, color=C_SUB)

# ── 밴드
band(6, 84, 148, 19, C_SURF_BAND)
band(6, 28, 148, 52, C_CAP_BAND)
band(6, 4, 148, 20, C_DATA_BAND)
ax.text(9, 100.2, "표면 — 사용자가 만나는 곳 (작업 성격에 맞는 UI 형태)",
        fontsize=10, fontproperties=F_BOLD, color=C_SURF_EDGE)
ax.text(9, 76.8, "능력 — 호출당하는 그래프/함수 (챗봇 아님)",
        fontsize=10, fontproperties=F_BOLD, color=C_CAP_EDGE)
ax.text(9, 20.8, "데이터 서비스 — CRUD·검색 (저장에 LLM 불필요, 번호로 능력과 대응)",
        fontsize=10, fontproperties=F_BOLD, color=C_DATA_EDGE)

# ── 표면 (y 86–96)
box(10, 36, 86, 96, "메인 챗 ④", "상시 대화형 · 얇은 라우터", ec=C_SURF_EDGE, done=True)
box(40, 78, 86, 96, "연구 워크플로우 ⑥→⑦", "단계형 · HITL · 장시간", ec=C_SURF_EDGE)
box(82, 116, 86, 96, "라이브러리", "관심사·논문·도구·노트 관리", ec=C_SURF_EDGE)
box(120, 150, 86, 96, "피드", "hype 뉴스 · 관심사 키워드 강조", ec=C_SURF_EDGE)

# ── 능력 Row A — 워크플로우 체인 + QA (y 58–69)
box(10, 30, 58, 69, "물리 QA", "Self-RAG · 현 그래프", done=True)
box(50, 66, 58, 69, "가설 수립", "문헌 기반")
box(70, 86, 58, 69, "실험 설계", "Plan-and-Execute")
box(90, 106, 58, 69, "실험 운영", "점검·추적·분석")
box(110, 126, 58, 69, "논문 작성", "Evaluator-Optimizer")

# ── 능력 Row B — 논문 3분할 + 공용 (y 40–51)
box(10, 28, 40, 51, "논문 요약기 ②a", "보유 전문 · lazy·캐시",
    ec=C_HUB_EDGE, fc=C_HUB, ts=9.5, ss=7, done=True)
box(31, 49, 40, 51, "논문 스크리닝 ②b", "abstract+지표 · 전문 X",
    ec=C_HUB_EDGE, fc=C_HUB, ts=9.5, ss=7)
box(52, 68, 40, 51, "논문 검색", "arxiv 어댑터 완료", ts=9.5, ss=7, done=True)
box(71, 87, 40, 51, "참고문헌 추천기", "문맥 기반 온디맨드", ts=9.5, ss=7)
box(90, 106, 40, 51, "문서 작성기 ①⑤", "대화→템플릿 · 공용", ts=9.5, ss=7)
box(109, 125, 40, 51, "추천 검색 ③", "관심사 트리거", ts=9.5, ss=7)
box(128, 141, 40, 51, "피드 수집", "cron · 태깅", ts=9.5, ss=7)
box(144, 154, 40, 51, "번역", "후처리", ts=9, ss=7)

# ── 데이터 (y 7–17)
box(10, 26, 7, 17, "코퍼스", "파인만 강의록", ec=C_DATA_EDGE, ts=9.5, ss=7, done=True)
box(28, 46, 7, 17, "논문 VDB ②", "전문 청크 + 요약", ec=C_DATA_EDGE, ts=9.5, ss=7, done=True)
box(48, 66, 7, 17, "논문 카탈로그", "DOI · 상태 · 지표", ec=C_DATA_EDGE, ts=9.5, ss=7)
box(68, 84, 7, 17, "관심사 저장소 ①", "VDB 컬렉션", ec=C_DATA_EDGE, ts=9.5, ss=7)
box(86, 102, 7, 17, "실험도구 DB ⑤", "구조화 레코드", ec=C_DATA_EDGE, ts=9.5, ss=7)
box(104, 120, 7, 17, "지식 노트", "user_note · 신뢰도 구분", ec=C_DATA_EDGE, ts=9.5, ss=7)
box(122, 138, 7, 17, "안전 규칙", "가드레일 공통 조회", ec=C_DATA_EDGE, ts=9.5, ss=7)

# ── 표면 → 능력
arrow((23, 85.6), (20, 69.6))          # 메인 챗 → 물리 QA
arrow((59, 85.6), (58, 69.6))          # 워크플로우 → 가설 수립
arrow((97, 85.6), (98, 51.6))          # 라이브러리 → 문서 작성기
arrow((110, 85.6), (117, 51.6))        # 라이브러리 → 추천 검색
arrow((137, 85.6), (135, 51.6))        # 피드 → 피드 수집

# ── 워크플로우 체인 + 재설계 루프
arrow((66.4, 63.5), (69.6, 63.5))
arrow((86.4, 63.5), (89.6, 63.5))
arrow((106.4, 63.5), (109.6, 63.5))
arrow((98, 69.7), (78, 69.7), color=C_DASH, ls=(0, (4, 3)), rad=0.35, lw=1.5)
ax.text(88, 74.3, "재실험: 설계만 재호출", ha="center", fontsize=8,
        fontproperties=F_REG, color=C_DASH)

# ── references 누적 리본
ax.text(84, 54.6,
        "가설·설계·운영이 참고문헌 추천기 호출 → references 누적(서지+인용 이유+단계) → 논문 작성이 소비",
        ha="center", fontsize=8, fontproperties=F_REG, color="#7A5230", style="italic")

# ── 논문 능력 간 연결
arrow((71, 45.5), (68.4, 45.5), color=C_DASH, ls=(0, (4, 3)), lw=1.5)   # 추천기 → 검색
arrow((52, 44), (49.4, 44), color=C_DASH, ls=(0, (4, 3)), lw=1.5)       # 검색 → ②b
arrow((109, 43), (49.4, 42), color=C_DASH, ls=(0, (4, 3)), rad=0.06, lw=1.3)  # ③ → ②b
ax.text(19, 37.6, "②a 호출: 라이브러리·QA·⑦", ha="center", fontsize=8,
        fontproperties=F_REG, color=C_HUB_EDGE)
ax.text(80, 37.0, "②b 호출: ③·참고문헌 추천기", ha="center", fontsize=8,
        fontproperties=F_REG, color=C_HUB_EDGE)

# ── 능력 → 데이터
arrow((16, 57.6), (15, 17.6), color=C_DATA_ARROW, lw=1.5)                      # QA → 코퍼스
arrow((24, 57.6), (33, 17.6), color=C_DATA_ARROW, lw=1.2, ls=(0, (4, 3)))      # QA → 논문 VDB
arrow((19, 39.6), (37, 17.6), color=C_DATA_ARROW, lw=1.5)                      # ②a → 논문 VDB
arrow((44, 39.6), (54, 17.6), color=C_DATA_ARROW, lw=1.5)                      # ②b → 카탈로그
arrow((96, 39.6), (77, 17.6), color=C_DATA_ARROW, lw=1.5)                      # 작성기 → 관심사
arrow((101, 39.6), (93, 17.6), color=C_DATA_ARROW, lw=1.5)                     # 작성기 → 실험도구
arrow((115, 39.6), (61, 17.6), color=C_DATA_ARROW, lw=1.2, ls=(0, (4, 3)))     # ③ → 카탈로그

plt.savefig(OUT, bbox_inches="tight", facecolor="white")
print(f"saved: {OUT}")
