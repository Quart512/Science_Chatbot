# -*- coding: utf-8 -*-
"""docs/architecture.png 생성 스크립트 — 표면/능력/데이터 3층 아키텍처 다이어그램.

설계가 바뀌면 이 파일의 box(...) 정의만 고치고 다시 실행한다:
    uv run docs/draw_architecture.py

--- 배치 규칙 (화살표가 박스에 가려지지 않게 하는 이유) ---
박스는 zorder=3, 화살표는 zorder=2라 둘이 겹치면 화살표가 숨는다. 그래서 좌표를
아무렇게나 두면 "그린 줄 알았는데 안 보이는" 선이 생긴다(실제로 겪음). 두 가지 규칙:

1. 능력 층을 두 줄로 나눈다 — 위(Row B1)에 소비자(참고문헌 추천기·추천 검색 ③),
   바로 아래(Row B2)에 그들이 공유하는 부품(논문 검색·스크리닝 ②b). 호출 관계가
   위→아래 짧은 화살표가 되어 다른 박스를 가로지를 일이 없다. 예전엔 이 다섯 개가
   한 줄에 있어서 ③ → ②b 화살표가 사이에 낀 박스 두 개를 관통해 안 보였다.
2. 층을 가로지르는 세로 화살표는 윗줄 박스 "사이 틈"으로 지나가게 x를 잡는다
   (예: 라이브러리 → 문서 작성기는 실험 운영과 논문 작성 사이 x≈108로 내려간다).

한글 폰트가 필요하다. FONT_CANDIDATES를 환경에 맞게 바꿀 것.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.font_manager import FontProperties

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


# ── 제목 + 범례
ax.text(80, 106.0, "Science Chatbot — 목표 아키텍처 (표면 / 능력 / 데이터 3층)",
        ha="center", va="center", fontsize=15, fontproperties=F_BOLD, color=C_TEXT)
ax.text(80, 103.6, "굵은 테두리 = 구현 완료 · 얇은 테두리 = 계획",
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

# ── 능력 Row A — 물리 QA + 연구 워크플로우 체인 (y 58–69)
box(10, 30, 58, 69, "물리 QA", "Self-RAG · 현 그래프", done=True)
box(50, 66, 58, 69, "가설 수립", "문헌 기반")
box(70, 86, 58, 69, "실험 설계", "Plan-and-Execute")
box(90, 106, 58, 69, "실험 운영", "점검·추적·분석")
box(110, 126, 58, 69, "논문 작성", "Evaluator-Optimizer")

# ── 능력 Row B1 — 소비자·독립 능력 (y 43–53)
box(56, 74, 43, 53, "참고문헌 추천기", "문맥 기반 온디맨드", ts=9.5, ss=7)
box(78, 96, 43, 53, "추천 검색 ③", "관심사 트리거", ts=9.5, ss=7)
box(100, 118, 43, 53, "문서 작성기 ①⑤", "대화→템플릿 · 공용", ts=9.5, ss=7)
box(122, 136, 43, 53, "피드 수집", "cron · 태깅", ts=9.5, ss=7)
box(140, 152, 43, 53, "번역", "후처리", ts=9, ss=7)

# ── 능력 Row B2 — 논문 처리 부품 (y 30–40). B1의 소비자 바로 아래에 둬서
#    호출 화살표가 짧은 수직선이 되게 한다(모듈 docstring "배치 규칙" 참고)
box(34, 52, 30, 40, "논문 요약기 ②a", "보유 전문 · lazy·캐시",
    ec=C_HUB_EDGE, fc=C_HUB, ts=9.5, ss=7, done=True)
box(56, 74, 30, 40, "논문 검색", "arxiv 어댑터 완료", ts=9.5, ss=7, done=True)
box(78, 96, 30, 40, "논문 스크리닝 ②b", "abstract+지표 · 전문 X",
    ec=C_HUB_EDGE, fc=C_HUB, ts=9.5, ss=7)

# ── 데이터 (y 7–17) — 소비하는 능력 바로 아래에 오도록 순서를 맞춤
box(10, 26, 7, 17, "코퍼스", "파인만 강의록", ec=C_DATA_EDGE, ts=9.5, ss=7, done=True)
box(28, 46, 7, 17, "논문 VDB ②", "전문 청크 + 요약", ec=C_DATA_EDGE, ts=9.5, ss=7, done=True)
box(48, 66, 7, 17, "논문 카탈로그", "DOI · 상태 · 지표", ec=C_DATA_EDGE, ts=9.5, ss=7)
box(68, 84, 7, 17, "지식 노트", "user_note · 신뢰도 구분", ec=C_DATA_EDGE, ts=9.5, ss=7)
box(86, 102, 7, 17, "관심사 저장소 ①", "VDB 컬렉션", ec=C_DATA_EDGE, ts=9.5, ss=7)
box(104, 120, 7, 17, "실험도구 DB ⑤", "구조화 레코드", ec=C_DATA_EDGE, ts=9.5, ss=7)
box(122, 138, 7, 17, "안전 규칙", "가드레일 공통 조회", ec=C_DATA_EDGE, ts=9.5, ss=7)

# ── 표면 → 능력 (Row A를 가로지르는 것들은 박스 사이 틈으로 내려간다)
arrow((23, 85.6), (20, 69.6))            # 메인 챗 → 물리 QA
arrow((59, 85.6), (58, 69.6))            # 연구 워크플로우 → 가설 수립
arrow((88, 85.6), (88, 53.6))            # 라이브러리 → 추천 검색 ③ (실험설계·실험운영 사이 틈)
arrow((108, 85.6), (108, 53.6))          # 라이브러리 → 문서 작성기 (실험운영·논문작성 사이 틈)
arrow((135, 85.6), (129, 53.6))          # 피드 → 피드 수집 (Row A 오른쪽 바깥)

# ── 워크플로우 체인 + 재설계 루프
arrow((66.4, 63.5), (69.6, 63.5))
arrow((86.4, 63.5), (89.6, 63.5))
arrow((106.4, 63.5), (109.6, 63.5))
arrow((98, 69.7), (78, 69.7), color=C_DASH, ls=(0, (4, 3)), rad=0.35, lw=1.5)
ax.text(88, 74.3, "재실험: 설계만 재호출", ha="center", fontsize=8,
        fontproperties=F_REG, color=C_DASH)

# ── references 누적 리본
ax.text(88, 55.5,
        "가설·설계·운영이 참고문헌 추천기 호출 → references 누적(서지+인용 이유+단계) → 논문 작성이 소비",
        ha="center", fontsize=8, fontproperties=F_REG, color="#7A5230", style="italic")

# ── Row B1 → Row B2 (소비자 → 공유 부품) + 부품 내부 체인
arrow((65, 42.6), (65, 40.4), color=C_DASH, ls=(0, (4, 3)), lw=1.5)   # 참고문헌 추천기 → 논문 검색
arrow((84, 42.6), (72, 40.4), color=C_DASH, ls=(0, (4, 3)), lw=1.5)   # 추천 검색 ③ → 논문 검색
arrow((74.4, 35), (77.6, 35), color=C_DASH, ls=(0, (4, 3)), lw=1.5)   # 논문 검색 → ②b 스크리닝
arrow((28, 58.4), (40, 40.4), color=C_DASH, ls=(0, (4, 3)), lw=1.5)   # 물리 QA → ②a (요약 필요 시)

ax.text(20, 47.5, "②a 호출: 라이브러리 · QA · ⑦", ha="center", fontsize=8,
        fontproperties=F_REG, color=C_HUB_EDGE)
ax.text(124, 35, "②b 호출: ③ · 참고문헌 추천기", ha="center", fontsize=8,
        fontproperties=F_REG, color=C_HUB_EDGE)

# ── 능력 → 데이터
arrow((16, 57.6), (16, 17.6), color=C_DATA_ARROW, lw=1.5)                   # 물리 QA → 코퍼스
arrow((22, 57.6), (33, 17.6), color=C_DATA_ARROW, lw=1.2, ls=(0, (4, 3)))   # 물리 QA → 논문 VDB(참고 부착)
arrow((40, 29.6), (38, 17.6), color=C_DATA_ARROW, lw=1.5)                   # ②a → 논문 VDB
arrow((85, 29.6), (62, 17.6), color=C_DATA_ARROW, lw=1.5)                   # ②b → 논문 카탈로그
arrow((104, 42.6), (96, 17.6), color=C_DATA_ARROW, lw=1.5)                  # 문서 작성기 → 관심사 ①
arrow((114, 42.6), (112, 17.6), color=C_DATA_ARROW, lw=1.5)                 # 문서 작성기 → 실험도구 ⑤

plt.savefig(OUT, bbox_inches="tight", facecolor="white")
print(f"saved: {OUT}")
