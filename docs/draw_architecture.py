# -*- coding: utf-8 -*-
"""docs/architecture.png 생성 스크립트 — 화면/기능/저장 3층 구조도.

구조가 바뀌면 이 파일의 box(...) 정의만 고치고 다시 실행한다:
    uv run docs/draw_architecture.py

--- 배치 규칙 (왜 이렇게 놓았는가) ---
1. **라이브러리를 가운데 둔다.** 라이브러리의 기능(논문 추출기·논문 찾기·등록 폼
   채우기)은 메인 챗과 연구 워크플로우 양쪽이 같이 쓰는 공용 부품이다. 가운데 두면
   양쪽으로 가는 화살표가 전부 짧아진다 — 예전엔 라이브러리가 오른쪽 끝에 있어서
   공용 관계를 그리려면 화면을 가로지르는 긴 선이 필요했다.
2. **연구 워크플로우 5단계는 세로로 쌓는다.** 가로로 늘어놓으면 그것만으로 가로폭을
   다 먹어서 다른 기둥이 쓸 자리가 없어진다(가로 배치였던 예전 그림의 문제).
3. **세로 화살표는 기둥 사이 "복도"로 지나가게 x를 잡는다.** 기둥은 zorder=3,
   화살표는 zorder=2라 겹치면 화살표가 박스 뒤로 숨는다. 복도는 x≈52~66과
   x≈106~128 두 곳.
4. **가로 화살표는 세로로 쌓인 박스들의 "틈" y로 지나가게 한다.** 워크플로우 단계
   사이 틈이 그 통로다.

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

C_SCREEN_BAND = "#EEF3FA"; C_SCREEN_EDGE = "#3B6EA5"
C_FUNC_BAND   = "#F3F0FA"; C_FUNC_EDGE   = "#6B4FA0"
C_STORE_BAND  = "#EFF7EF"; C_STORE_EDGE  = "#3E7A4C"
C_SHARED      = "#FBEEDB"; C_SHARED_EDGE = "#C07A2D"
C_TEXT = "#1F2430"; C_SUB = "#5A6270"
C_FLOW = "#44506B"        # 화면 → 기능, 단계 → 단계
C_SHARE_ARROW = "#C07A2D" # 라이브러리 기능이 다른 화면에 쓰이는 관계
C_STORE_ARROW = "#5B8A67" # 기능 → 저장

fig, ax = plt.subplots(figsize=(17, 11), dpi=150)
ax.set_xlim(0, 180); ax.set_ylim(0, 106)
ax.axis("off")
fig.patch.set_facecolor("white")


def band(x, y, w, h, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc=fc, ec="none", zorder=1))


def group_frame(x0, x1, y0, y1, ec):
    """여러 박스를 하나의 묶음으로 보이게 하는 옅은 테두리(화살표 없이 소속만 표시)."""
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc="none", ec=ec, lw=1.2, ls=(0, (5, 4)),
                                alpha=0.55, zorder=1.5))


def box(x0, x1, y0, y1, title, sub=None, ec=C_FUNC_EDGE, fc="white", ts=10, ss=7.5):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                boxstyle="round,pad=0.25,rounding_size=0.8",
                                fc=fc, ec=ec, lw=2.0, zorder=3))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if sub:
        ax.text(cx, cy + 1.3, title, ha="center", va="center", fontsize=ts,
                fontproperties=F_BOLD, color=C_TEXT, zorder=4)
        ax.text(cx, cy - 1.9, sub, ha="center", va="center", fontsize=ss,
                fontproperties=F_REG, color=C_SUB, zorder=4)
    else:
        ax.text(cx, cy, title, ha="center", va="center", fontsize=ts,
                fontproperties=F_BOLD, color=C_TEXT, zorder=4)


def arrow(p0, p1, color=C_FLOW, lw=1.8, ls="solid"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13,
                                 color=color, lw=lw, linestyle=ls, zorder=2))


def label(x, y, text, color, bg, fs=7.2, bold=False):
    """설명 문구. 배경색을 깔아 밑을 지나는 선 위에서도 읽히게 한다 — 좁은 복도에
    글자를 넣다 보면 어떻게 좌표를 잡아도 어떤 선과는 겹치기 때문."""
    ax.text(x, y, text, ha="center", va="center", fontsize=fs,
            fontproperties=F_BOLD if bold else F_REG, color=color, zorder=5,
            bbox=dict(facecolor=bg, edgecolor="none", boxstyle="round,pad=0.35"))


def elbow(points, color=C_FLOW, lw=1.8, ls="solid"):
    """꺾인 경로. 마지막 구간에만 화살표를 붙이고 앞 구간은 선으로 잇는다.

    직선으로 그으면 박스를 관통하는 연결(예: 등록 폼 채우기 → 메인 챗)을 복도로
    돌리기 위한 것 — matplotlib의 connectionstyle은 꺾임을 한 번밖에 못 줘서
    직접 waypoint를 찍는다.
    """
    for a, b in zip(points, points[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, ls=ls,
                zorder=2, solid_capstyle="round")
    arrow(points[-2], points[-1], color=color, lw=lw, ls=ls)


# ── 제목
ax.text(90, 103.5, "AIsaac — 구조", ha="center", va="center",
        fontsize=16, fontproperties=F_BOLD, color=C_TEXT)
ax.text(90, 100.6, "화면(사용자가 보는 것) / 기능(뒤에서 일하는 것) / 저장(남는 것)",
        ha="center", va="center", fontsize=9.5, fontproperties=F_REG, color=C_SUB)

# ── 밴드 (라벨은 박스 위 여백에 둔다 — 박스와 같은 y에 두면 가려진다)
band(6, 83, 168, 15, C_SCREEN_BAND)
band(6, 25, 168, 55, C_FUNC_BAND)
band(6, 2, 168, 20, C_STORE_BAND)
ax.text(9, 96.2, "화면 — 사용자가 만나는 곳", va="center",
        fontsize=10.5, fontproperties=F_BOLD, color=C_SCREEN_EDGE, zorder=5)
ax.text(9, 78.0, "기능 — 화면 뒤에서 실제 일을 하는 것 (버튼을 누르거나 질문할 때 그때 동작)", va="center",
        fontsize=10.5, fontproperties=F_BOLD, color=C_FUNC_EDGE, zorder=5)
ax.text(9, 19.9, "저장 — 어디에 무엇이 남는가    VDB = 뜻이 비슷한 걸 찾아주는 검색용 · RDB = 목록·상태를 관리하는 표",
        va="center", fontsize=10.5, fontproperties=F_BOLD, color=C_STORE_EDGE, zorder=5,
        bbox=dict(facecolor=C_STORE_BAND, edgecolor="none", boxstyle="round,pad=0.4"))

# ── 화면 (y 84.5–94)
box(10, 52, 84.5, 94, "메인 챗", "궁금한 걸 물어본다", ec=C_SCREEN_EDGE, ts=11)
box(66, 106, 84.5, 94, "라이브러리", "논문·관심사·도구·노트 관리", ec=C_SCREEN_EDGE, ts=11)
box(128, 168, 84.5, 94, "연구 워크플로우", "연구를 단계별로 진행", ec=C_SCREEN_EDGE, ts=11)

# ── 기능: 왼쪽 기둥 — 메인 챗이 쓰는 것
box(10, 52, 62, 74, "과학 Q&A",
    "자료를 찾아 답하고, 스스로 점검해\n부족하면 다시 찾아 고쳐 쓴다", ts=11, ss=8)

# ── 기능: 가운데 기둥 — 라이브러리의 기능.
# 양쪽(메인 챗·연구 워크플로우)이 같이 쓰는 공용 부품이라 일부러 가운데 둔다.
# 소속은 화살표 대신 옅은 묶음 테두리로 표시한다 — 화살표로 그리면 이 좁은 복도에
# 선이 세 개 더 늘어 다른 관계선과 엉킨다(1차 렌더에서 실제로 엉켰다).
group_frame(63, 109, 38, 76, C_SHARED_EDGE)
box(66, 106, 65, 73, "논문 추출기", "전문을 읽고 핵심 주장·근거·한계 정리",
    ec=C_SHARED_EDGE, fc=C_SHARED, ts=10, ss=7.5)
box(66, 106, 53, 61, "논문 찾기", "arXiv에서 검색 + 관련도 선별",
    ec=C_SHARED_EDGE, fc=C_SHARED, ts=10, ss=7.5)
box(66, 106, 41, 49, "등록 폼 채우기", "대화 내용으로 폼을 미리 채워줌",
    ec=C_SHARED_EDGE, fc=C_SHARED, ts=10, ss=7.5)

# ── 기능: 오른쪽 기둥 — 연구 워크플로우 5단계 (세로로 쌓아 가로폭을 아낀다)
box(128, 168, 66, 73, "① 가설 수립", "검증 가능한 가설 + 근거", ts=10, ss=7.5)
box(128, 168, 56.5, 63.5, "② 실험 설계", "무엇을 바꾸고 무엇을 잴지", ts=10, ss=7.5)
box(128, 168, 47, 54, "③ 실험 운영", "내가 낸 결과를 해석·판정", ts=10, ss=7.5)
box(128, 168, 37.5, 44.5, "④ 실험 보고서", "앞 단계를 사실 그대로 정리", ts=10, ss=7.5)
box(128, 168, 28, 35, "⑤ 논문 초안", "제목·초록·서론·방법·결과·고찰", ts=10, ss=7.5)

# ── 저장 (y 4.5–16.5). 순서는 "그걸 쓰는 기능 바로 아래"가 되게 잡는다 —
# 그래야 초록 화살표가 다른 기둥을 관통하지 않는다.
box(10, 40, 4.5, 16.5, "파인만 강의록", "VDB", ec=C_STORE_EDGE, ts=10, ss=8)
box(43, 73, 4.5, 16.5, "논문 내용 · 목록", "VDB(내용) + RDB(목록·상태)",
    ec=C_STORE_EDGE, ts=10, ss=7.5)
box(76, 106, 4.5, 16.5, "관심사 · 실험도구 · 노트", "RDB (노트는 검색용 VDB도)",
    ec=C_STORE_EDGE, ts=9.5, ss=7.5)
box(109, 139, 4.5, 16.5, "library/ 폴더", "원본 PDF를 파일 그대로",
    ec=C_STORE_EDGE, ts=10, ss=7.5)
box(142, 172, 4.5, 16.5, "연구 기록", "RDB · 단계별로 남아 되돌아갈 수 있다",
    ec=C_STORE_EDGE, ts=10, ss=7)

# ── 화면 → 기능
arrow((25, 84.1), (25, 74.4))            # 메인 챗 → 과학 Q&A
arrow((86, 84.1), (86, 76.4))            # 라이브러리 → 기능 묶음
arrow((148, 84.1), (148, 73.4))          # 연구 워크플로우 → 가설 수립

# ── 워크플로우 단계 체인 (세로)
for y0, y1 in [(66, 63.5), (56.5, 54), (47, 44.5), (37.5, 35)]:
    arrow((148, y0 - 0.3), (148, y1 + 0.3))

# ── 라이브러리 기능이 다른 화면에서도 쓰인다 (기둥 사이 틈으로 지나간다)
arrow((65.6, 69), (52.4, 69), color=C_SHARE_ARROW, lw=1.7)      # 논문 추출기 → 과학 Q&A
label(60, 71.8, "등록해둔 논문을\n답변 근거로", C_SHARE_ARROW, C_FUNC_BAND)

arrow((106.4, 58), (127.6, 60), color=C_SHARE_ARROW, lw=1.7)    # 논문 찾기 → 실험 설계
label(118, 64.5, "각 단계의\n참고문헌 추천", C_SHARE_ARROW, C_FUNC_BAND)

# 등록 폼 채우기 → 메인 챗: 직선으로는 과학 Q&A를 관통하므로 왼쪽 복도(x=53.5)로 돌린다
elbow([(65.6, 45), (53.5, 45), (53.5, 81), (37, 81), (37, 84.1)],
      color=C_SHARE_ARROW, lw=1.7)
label(46, 82.4, "챗 대화를 읽어서", C_SHARE_ARROW, "white")

# ── 기능 → 저장 (같은 목적지로 가는 선끼리 안 엉키게 복도 x를 나눠 쓴다)
arrow((22, 61.6), (22, 16.9), color=C_STORE_ARROW, lw=1.5)      # 과학 Q&A → 파인만 강의록
arrow((46, 61.6), (52, 16.9), color=C_STORE_ARROW, lw=1.5)      # 과학 Q&A → 논문 내용
arrow((65.6, 67), (60, 16.9), color=C_STORE_ARROW, lw=1.5)      # 논문 추출기 → 논문 내용·목록
arrow((65.6, 55), (66, 16.9), color=C_STORE_ARROW, lw=1.5)      # 논문 찾기 → 논문 목록
arrow((86, 40.6), (88, 16.9), color=C_STORE_ARROW, lw=1.5)      # 등록 폼 채우기 → 관심사·도구
# 논문 추출기 → library/ 폴더: 아래로 곧장 내리면 논문 찾기·등록 폼을 관통하므로
# 오른쪽 복도(x 109~128)를 타고 내려간다.
arrow((106.4, 69), (118, 16.9), color=C_STORE_ARROW, lw=1.5)
arrow((127.6, 60), (100, 16.9), color=C_STORE_ARROW, lw=1.5)    # 실험 설계 → 실험도구 조회
arrow((152, 27.6), (155, 16.9), color=C_STORE_ARROW, lw=1.5)    # 워크플로우 → 연구 기록

# ── 각주
ax.text(9, 0.3, "아직 없는 것 — 피드(관심 분야 최신 소식 모아보기) · 번역 레이어(답변을 한국어로 한 번 더 다듬기)",
        fontsize=8, fontproperties=F_REG, color=C_SUB)

plt.savefig(OUT, bbox_inches="tight", facecolor="white")
print(f"saved: {OUT}")
