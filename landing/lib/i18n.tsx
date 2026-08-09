"use client"

import { createContext, useContext, useState, type ReactNode } from "react"

export type Lang = "ko" | "en"

type Dict = Record<Lang, string>

// Every UI string is defined for both languages.
export const dict = {
  // Nav
  // 08-08 — "달의 뒷면"은 섹션째 없앴다. "미정복 영역"이라는 이미지가 제일 강한데
  // 기능에 붙이는 순간 그 이미지가 죽는다(RoadMap "08-08 결론" 참고). 컨셉은
  // 골방·프리즘·궤도 셋뿐이고, 컨셉이 둘(프리즘·궤도)이라 섹션 번호도 안 붙인다.
  "nav.prism": { ko: "프리즘", en: "Prism" },
  "nav.orbit": { ko: "궤도", en: "Orbit" },
  "nav.screens": { ko: "화면", en: "Screens" },
  "nav.archive": { ko: "아카이브", en: "Archive" },
  "nav.launch": { ko: "다운로드", en: "Download" },

  // Hero
  // 08-06 — "가동 중"/"online"은 상시 접속 가능한 호스팅 서비스처럼 읽히는데
  // AIsaac은 사용자가 내려받아 자기 컴퓨터에서 돌리는 로컬 앱이라 사실과 다르다
  // (텔레메트리 자체를 안 보낸다는 RoadMap 로깅 설계 노트와 같은 이유 — "가동 중"을
  // 판단할 서버가 없다). 실제 배포 형태를 그대로 적는다.
  // 08-08 — "자율형"을 뺐다. 연구 워크플로우는 단계 전환을 사용자가 직접 누르고
  // 실험도 사람이 직접 하는데(README) 자율이라고 적혀 있던 건 사실이 아니다.
  // 그렇다고 "매번 눌러야 한다"를 카피로 드러내지도 않는다(사용자 결정) —
  // 자율이라고도 개입하라고도 말하지 않고, 배지는 무대(골방·1665)만 가리킨다.
  "hero.status": { ko: "골방 · 1665", en: "A room of one's own · 1665" },
  // 08-07 — "뉴턴처럼 분해하고, 스스로 진실을 포착하다"는 v0.app이 임의로 지은
  // 문구였다(사용자 피드백 — 원래 병합 지시는 "슬로건은 1(제미나이 브랜드 초안)을
  // 병합"이었는데 이 부분만 안 지켜져 있었음). RoadMap 부록 "1. 제미나이가 작성한
  // 브랜드/README 초안"의 실제 승인된 메인 슬로건("AIsaac / Analyze. Discover.
  // Orbit. / Turning the dark side of knowledge into a perfect scientific
  // orbit.")으로 교체 — 세 동사(Analyze/Discover/Orbit)는 브랜드 고정 문구라 언어
  // 무관하게 영어 그대로 두고, 그 아래 서브라인만 KO/EN 각각 번역해 둔다.
  // 08-08 — `Analyze. Discover. Orbit.` 3동사 구조를 폐기했다. 3동사와 3기능을
  // 나란히 두면 독자가 1:1 대응을 기대하는데 그게 계속 안 맞았고(세 번 실패),
  // 원인이 매핑이 아니라 구조 자체였다. 새 슬로건은 한 문장이 두 가지를 동시에
  // 한다 — 풀네임으로 AIsaac 어원을 해명하고("아이작 뉴턴"), "당신의 컴퓨터
  // 안에서"로 로컬 실행을 흡수한다.
  "hero.title.a": { ko: "아이작 뉴턴의 1665년을", en: "Isaac Newton's 1665," },
  "hero.title.b": { ko: "당신의 컴퓨터 안에서.", en: "inside your computer." },
  // 08-07 — "혼돈스러운 날것의 아이디어를 완벽한 지식의 스펙트럼으로 전환합니다"
  // 같은 표현이 알아듣기 힘들다는 지적 — 프리즘 은유를 문장 안에 욱여넣지 않고,
  // 실제로 무엇을 하는 서비스인지 평서문으로 먼저 말한다(제미나이 초안의 소개
  // 문단을 뼈대로 축약).
  // 08-08 — 대상 셋을 나열하는 구조가 핵심이다. "골방"만 내세우면 이미지가
  // 부정적으로 읽히고 사용자층도 좁아지는데, 여러 대상 사이에 놓이면 덜 튄다.
  // 1665를 해명하는 역사 설명(흑사병·시골 본가)은 일부러 안 넣었다 —
  // 서비스 설명이 그 자리를 대신하면 1665는 수수께끼가 아니라 분위기가 된다.
  "hero.desc": {
    ko: "AIsaac(아이작)은 골방의 대학원생, 연구실의 전문 연구자, 밤하늘을 보며 의문을 품는 취미 과학자를 위한 AI 연구 어시스턴트입니다. 혼자 붙잡고 있던 질문을 끝까지 밀고 나가도록 돕습니다.",
    en: "AIsaac is an AI research assistant for the graduate student working alone, the researcher in the lab, and the hobbyist who looks up at the night sky and wonders. It helps you carry a question you've been holding onto all the way through.",
  },
  "hero.tagline": {
    ko: "골방의 질문을 논문으로.",
    en: "From a question in a small room to a finished paper.",
  },
  "hero.cta.primary": { ko: "다운로드", en: "Download" },
  "hero.cta.secondary": { ko: "궤도 살펴보기", en: "Explore the orbit" },
  // 08-06 — 원래 가짜 사용량 숫자(10,482 등)였다. AIsaac은 텔레메트리를 안 보내
  // 원리적으로 실사용 통계를 낼 방법이 없어서(로깅 설계 노트 참고) 지어낸 숫자
  // 대신 실제로 참인 특징 3가지로 바꿨다.
  // 08-08 — 원래 3칸이었고 가운데가 "지원 플랫폼 / macOS·Win·Linux"였는데, 좁은
  // 화면에서 그 칸만 글자가 잘렸다(3칸에 고정폭 글꼴이라 제일 긴 값이 먼저 터진다).
  // 플랫폼은 다운로드 버튼 바로 위(CTA)가 더 맞는 자리라 그리로 옮기고 여긴 2칸으로
  // 줄였다 — 08-06에 가짜 사용량 숫자를 대체한 "실제로 참인 특징"이라는 성격은 그대로다.
  "hero.metric.1.label": { ko: "실행 방식", en: "Runs" },
  "hero.metric.1.value": { ko: "100% 로컬", en: "100% local" },
  "hero.metric.2.label": { ko: "데이터 저장 위치", en: "Your data" },
  "hero.metric.2.value": { ko: "내 컴퓨터에만", en: "Stays on-device" },

  // Prism section
  // 08-08 — 프리즘이 대응하는 기능은 물리 QA가 아니라 논문 추출기다. 자유 텍스트를
  // 결정론적 스키마로 가르는 걸 실제로 해내는 유일한 기능이고, "색은 프리즘이 만든
  // 게 아니라 원래 빛 안에 있었다"는 뉴턴의 결론이 설계 원칙("판정이 아니라 추출",
  // CLAUDE.md §3)과 그대로 겹친다. 옛 카피의 "숨은 인과관계를 찾아낸다"는 실제로
  // 하지 않는 일이라 뺐다.
  "prism.kicker": { ko: "프리즘", en: "Prism" },
  "prism.title": { ko: "논문을 분석, 추출, 정리한다", en: "Analyze, extract, organize" },
  // 08-08 후속(사용자 지적) — 원래 한 문장이었는데 두 문장이 하는 말이 서로 다르다
  // (① 지금 무엇을 하는가 ② 등록해두면 나중에 뭐가 좋아지는가). 줄바꿈으로 갈라서
  // 읽을 때 두 생각으로 갈리게 한다 — `hero.title.a/b`와 같은 패턴.
  "prism.desc.a": {
    ko: "저자가 논문에서 말하고 있는 것을 추출해 정리합니다.",
    en: "It extracts and organizes what the authors themselves state in the paper.",
  },
  "prism.desc.b": {
    ko: "등록해둔 논문은 챗봇이 답할 때 근거로 인용합니다.",
    en: "Registered papers are then cited as evidence when the chat answers you.",
  },
  "prism.feature": { ko: "논문 추출기", en: "Paper extractor" },
  "prism.beam.label": { ko: "백색광 입력", en: "White beam in" },
  // 다섯 갈래는 지어낸 이름이 아니라 `paper/paper_extraction.py`의 `PaperExtraction`
  // 필드 그대로다 — 스펙트럼 5색과 필드 5개가 우연히 맞아떨어졌다.
  "prism.band.red": { ko: "핵심 주장", en: "Core claims" },
  "prism.band.yellow": { ko: "근거", en: "Evidence" },
  "prism.band.green": { ko: "저자가 밝힌 한계", en: "Author-stated limitations" },
  "prism.band.blue": { ko: "남은 질문", en: "Open questions" },
  "prism.band.violet": { ko: "코드·데이터 공개", en: "Code & data availability" },

  // Orbit section
  // 08-08 — 궤도는 자율의 은유가 아니다. 중심으로 계속 이끌려 떨어지는 것과 앞으로
  // 나아가는 것의 균형이 궤도이고, 그게 앱의 실제 동작과 맞다. 그래서 "매번 명령을
  // 내리지 않아도 됩니다"·"End-to-End 자율 루프"를 전부 걷어내고, 워크플로우가 파는
  // 것(전 과정)과 궤도의 이미지(한 바퀴)를 제목 한 줄에서 직접 잇는다.
  // 노드도 지어낸 4개(자료 수집·분석·정리·검증)가 아니라 실제 워크플로우 5단계다.
  "orbit.kicker": { ko: "궤도", en: "Orbit" },
  "orbit.title": { ko: "가설에서 논문까지, 한 바퀴를 끝까지", en: "From hypothesis to paper, all the way around" },
  "orbit.desc": {
    ko: "아이디어를 정리하고, 실험하여 논문으로 완성하는 전 과정을 함께합니다. 연구를 시작하면 가설 수립 · 실험 설계 · 실험 운영 · 실험 보고서 · 논문 초안까지 다섯 단계가 이어집니다.",
    en: "It goes with you through the whole arc — shaping an idea, running the experiment, finishing the paper. Once a research topic starts, five stages follow: hypothesis, experiment design, running it, the report, and the paper draft.",
  },
  "orbit.node.1": { ko: "가설 수립", en: "Hypothesis" },
  "orbit.node.2": { ko: "실험 설계", en: "Experiment design" },
  "orbit.node.3": { ko: "실험 운영", en: "Running it" },
  "orbit.node.4": { ko: "실험 보고서", en: "Report" },
  "orbit.node.5": { ko: "논문 초안", en: "Paper draft" },
  "orbit.core": { ko: "연구 주제 하나", en: "One research topic" },
  "orbit.loop": { ko: "연구 워크플로우", en: "Research workflow" },

  // Screens section (08-08 신설)
  // 08-08 진단 ② — 랜딩에 기능 섹션이 아예 없었다. `Hero → Prism → Orbit → CTA`뿐이라
  // 서비스를 소개하는 자리가 코드에 존재하지 않았고, "3 컨셉과 3 서비스가 안 이어진다"의
  // 실체가 사실 이거였다(은유가 허공에 떠 있던 것). 컨셉 섹션이 "연구를 어떻게 대하는가"면
  // 여기는 "무엇을 해주는가"라, 카피에서 은유를 전부 뺀 평서문으로만 쓴다 — 프리즘·궤도와
  // 같은 기능을 가리키는 탭(논문·연구 워크플로우)이 있어도 조작 수준으로만 말해 안 겹친다.
  //
  // 탭은 "기능"이 아니라 "화면"이다 — README의 기능 13개는 대부분 별도 화면 없이 버튼
  // 뒤에서 돌고(스크리닝·논문 검색·참고문헌 추천기는 아예 다른 기능 뒤에서 자동 동작),
  // 탭=기능으로 두면 "모든 기능"이 거짓이 된다.
  "screens.kicker": { ko: "화면", en: "Screens" },
  "screens.title": { ko: "무엇을 해주는가", en: "What it does" },
  // "실제 사이드바 그대로"라고는 안 쓴다 — 설정 화면은 `/download` 페이지와 겹쳐 여기서
  // 뺐으므로(로드맵 08-08 결론) 목록이 사이드바 전체라고 말하면 사실과 다르다.
  // 08-08 후속(사용자 지적) — "아래는 …입니다. 하나를 고르면 …을 보여줍니다"는 번역체다.
  // "아래는"으로 시작하는 지시대명사 문장도, "~을 보여줍니다"로 끝나는 사역형도
  // 한국어 문어에서는 잘 안 쓴다. 무엇이 있는지만 짧게 말하고, 눌러보라는 안내는
  // 바로 아래 힌트 문구가 이미 하고 있으니 여기서 두 번 하지 않는다.
  "screens.desc": {
    ko: "앱을 켜면 왼쪽에 이 화면들이 있습니다.",
    en: "These are the screens you'll find down the left side of the app.",
  },
  // 08-08 사용자 지적 — 목록이 클릭 가능하다는 걸 눈치 못 챌 수 있다. 첫 클릭 전까지만
  // 띄우고 그 뒤엔 사라진다(자리는 남겨 레이아웃이 안 흔들리게). 대안이던 "주기적 자동
  // 전환"은 기각 — 방문자가 패널을 읽는 도중에 글이 바뀌어, 눈치채게 만드는 대가로
  // 읽던 문장을 뺏는다.
  "screens.hint": { ko: "눌러서 확인하세요", en: "Click to explore" },
  "screens.group.main": { ko: "메인", en: "Main" },
  "screens.group.library": { ko: "라이브러리", en: "Library" },

  // 화면 이름은 앱 사이드바(`frontend-react/src/components/Layout.tsx`)와 글자까지 같게
  // 맞춘다 — 랜딩에서 본 이름이 앱에서 그대로 나와야 목록을 재현한 의미가 있다.
  "screens.home.name": { ko: "홈", en: "Home" },
  "screens.home.title": { ko: "지금 무엇이 쌓여 있는지", en: "What you've got so far" },
  "screens.home.desc": {
    ko: "관심사·논문·실험도구·노트가 몇 건인지, 마지막으로 하던 대화와 연구가 무엇이었는지를 한 화면에서 보고 바로 이어갑니다.",
    en: "See how many interests, papers, instruments and notes you've collected, and what conversation or research you were last in — then pick up where you left off.",
  },

  "screens.chat.name": { ko: "챗봇", en: "Chat" },
  // 08-08 후속(사용자 지적) — "물리 QA"는 두 군데가 낡았다: ① 08-06에 시스템
  // 프롬프트를 이미 "과학·수학"으로 넓혔는데(RoadMap "챗봇 시스템 프롬프트 물리
  // 편애 제거") 이 라벨만 안 따라갔다. ② "QA"는 원래 "Q&A"의 표기 오류였다.
  "screens.chat.title": { ko: "근거를 달고 답하는 과학 Q&A", en: "Science Q&A that shows its sources" },
  "screens.chat.desc": {
    ko: "등록해둔 논문과 노트, 필요하면 웹 검색까지 근거로 삼아 답합니다. 스스로 답을 점검해 부족하면 다시 찾아 고쳐 씁니다. 다른 화면을 보는 중에도 오른쪽 챗 패널로 같은 대화를 이어갑니다.",
    en: "It answers from the papers and notes you've registered, and searches the web when it needs to. It checks its own answer and looks again if it falls short. A chat panel stays open on the right, so you can keep the same conversation going from any screen.",
  },

  "screens.research.name": { ko: "연구 워크플로우", en: "Research workflow" },
  "screens.research.title": { ko: "다섯 단계를 이어서", en: "Five stages, one after another" },
  "screens.research.desc": {
    ko: "가설 수립 · 실험 설계 · 실험 운영 · 실험 보고서 · 논문 초안. 지나온 단계가 전부 남아 있어 과거 시점으로 돌아가 다른 갈래로 갈라질 수 있습니다.",
    en: "Hypothesis, experiment design, running it, the report, the paper draft. Every stage you've passed is kept, so you can go back to an earlier point and branch off in another direction.",
  },

  "screens.papers.name": { ko: "논문", en: "Papers" },
  "screens.papers.title": { ko: "등록하면 갈라서 보여줍니다", en: "Register one and it comes apart" },
  "screens.papers.desc": {
    ko: "PDF를 등록하면 핵심 주장 · 근거 · 저자가 밝힌 한계 · 남은 질문으로 갈라 정리합니다. 등록된 논문은 챗과 연구 워크플로우가 근거로 인용합니다.",
    en: "Register a PDF and it's separated into core claims, evidence, author-stated limitations and open questions. Registered papers are then cited as evidence by the chat and the research workflow.",
  },

  "screens.interests.name": { ko: "관심사", en: "Interests" },
  "screens.interests.title": { ko: "적어두면 논문을 찾아옵니다", en: "Write it down and it finds the papers" },
  "screens.interests.desc": {
    ko: "찾는 것 · 이미 아는 것 · 제외할 주제를 적어두면 arXiv에서 후보를 찾아 관련도순으로 정리합니다. peer review 여부 · 연도 · 인용수는 점수로 합치지 않고 그대로 보여줍니다 — 최종 판단은 직접 합니다.",
    en: "Write down what you're looking for, what you already know and what to leave out, and it finds candidates on arXiv, ordered by relevance. Peer-review status, year and citation counts are shown as they are, never folded into one score — the final call is yours.",
  },

  "screens.equipment.name": { ko: "실험도구", en: "Equipment" },
  "screens.equipment.title": { ko: "가진 장비를 전제로 설계합니다", en: "Designs around the gear you have" },
  "screens.equipment.desc": {
    ko: "이름 · 목적 · 세부내용 · 주의사항을 등록해두면 실험 설계 단계가 그 장비를 전제로 설계하고, 주의사항을 안내 맨 앞에 붙여줍니다.",
    en: "Register the name, purpose, details and cautions for the instruments you have, and the experiment-design stage plans around them, putting your cautions first in its guidance.",
  },

  "screens.notes.name": { ko: "지식 노트", en: "Notes" },
  "screens.notes.title": { ko: "직접 적은 것도 근거가 됩니다", en: "What you wrote counts as evidence too" },
  "screens.notes.desc": {
    ko: "강의록이나 메모를 적어두면 논문과 같은 방식으로 검색되어 챗과 연구 워크플로우가 참고합니다.",
    en: "Write down lecture notes or memos and they're searched the same way papers are, so the chat and the research workflow can draw on them.",
  },

  // CTA
  // 08-08 — "AIsaac이 나머지를 공전시킵니다"는 자율 주장이라 뺐다. 대신 실제로
  // 참인 것(내려받아 내 컴퓨터에서 돌린다)만 적는다.
  // 08-08 후속(사용자 지적) — ⓐ "설치 프로그램은 따로 없습니다"는 뺐다. 여기서 굳이
  // 할 말이 아니고(설치 절차는 /download 페이지가 이미 다 설명한다), 마지막 한 마디를
  // 없는 것 이야기로 끝내게 된다. EN도 같은 이유로 `There's no separate installer.`만
  // 덜어냈다. ⓑ 나머지 한국어 문장은 번역체라 다시 썼다 — "질문 하나로 시작하면
  // 됩니다"·"자기 컴퓨터에서 실행합니다"는 영어 문장 구조를 그대로 옮긴 티가 난다.
  // 한국어는 마지막 CTA에서 청유형으로 끝나는 게 자연스럽고(바로 아래가 다운로드
  // 버튼이다), 소유격도 "자기"가 아니라 "내"를 쓴다(히어로 배지의 "내 컴퓨터에만"과
  // 같은 어휘). 영어는 원래 문장이 어색하지 않아 그대로 둔다 — 두 언어가 서로 직역이
  // 아니라 각자 자연스러운 게 맞다.
  "cta.title": { ko: "질문 하나면 충분합니다.", en: "One question is enough to start." },
  // 지원 플랫폼은 원래 히어로 통계 타일에 있었는데 여기로 내렸다(08-08 사용자 결정) —
  // 다운로드 버튼 바로 위가 "내 OS로 받을 수 있나"에 답할 자리이고, 히어로의 3칸
  // 그리드에서는 좁은 화면에서 `macOS·Win·Linux`가 잘렸다. 아키텍처 제약(macOS는
  // Apple Silicon, Win·Linux는 x86_64)은 여기 안 적는다 — `/download`가 카드마다
  // 정확히 밝히고 있고, CTA 한 줄에 다 넣으면 읽히지도 않는다.
  "cta.desc": {
    ko: "내려받아 내 컴퓨터에서 실행하세요. macOS · Windows · Linux를 지원합니다.",
    en: "Download it and run it on your own computer. Available for macOS, Windows and Linux.",
  },
  "cta.button": { ko: "다운로드", en: "Download" },

  // Download page (08-07) — 08-06까지는 다운로드 버튼이 감지된 OS의 zip으로 바로
  // 걸려 있었는데, 설치 안내(압축 해제·실행 파일 위치)를 보여줄 자리가 없었고
  // Intel Mac처럼 감지가 틀리면 바로 안 되는 파일을 받게 되는 문제가 있었다 —
  // 중간에 전용 페이지(/download)를 두고 nav·hero·CTA 버튼을 전부 이 페이지로
  // 보낸 뒤, 실제 다운로드는 이 페이지 안에서 하게 함.
  "download.title": { ko: "다운로드", en: "Download" },
  "download.subtitle": {
    ko: "운영체제에 맞는 버전을 받아 압축을 풀고 실행하세요. 설치 프로그램은 따로 없습니다 — 폴더 안의 실행 파일을 더블클릭하면 바로 시작됩니다.",
    en: "Download the build for your OS, unzip it, and run it. There's no separate installer — just double-click the launcher inside the folder.",
  },
  "download.detected.none": {
    ko: "운영체제를 자동으로 인식하지 못했습니다. 아래에서 직접 선택해주세요.",
    en: "We couldn't detect your OS automatically. Please choose one below.",
  },
  "download.cta.macos": { ko: "macOS용 다운로드", en: "Download for macOS" },
  "download.cta.windows": { ko: "Windows용 다운로드", en: "Download for Windows" },
  "download.cta.linux": { ko: "Linux용 다운로드", en: "Download for Linux" },
  "download.intel.warning": {
    ko: "Intel Mac이 감지되었습니다 — 위 macOS 빌드는 Apple Silicon(M1 이상) 전용입니다. 아래 Docker 배포판을 이용해주세요.",
    en: "We detected an Intel Mac — the macOS build above is Apple Silicon (M1 or later) only. Please use the Docker version below.",
  },
  "download.all.title": { ko: "모든 버전", en: "All versions" },
  "download.platform.macos": { ko: "macOS", en: "macOS" },
  "download.arch.macos": { ko: "Apple Silicon (M1 이상)", en: "Apple Silicon (M1 or later)" },
  "download.platform.windows": { ko: "Windows", en: "Windows" },
  "download.arch.windows": { ko: "64비트 (x86_64)", en: "64-bit (x86_64)" },
  "download.platform.linux": { ko: "Linux", en: "Linux" },
  "download.arch.linux": { ko: "64비트 (x86_64)", en: "64-bit (x86_64)" },
  "download.platform.docker": { ko: "Docker", en: "Docker" },
  "download.arch.docker": {
    ko: "모든 아키텍처 · Intel Mac 포함",
    en: "Any architecture · including Intel Mac",
  },
  "download.card.button": { ko: "다운로드", en: "Download" },
  "download.install.title": { ko: "설치 방법", en: "How to install" },
  "download.install.step1": { ko: "위 버튼으로 압축 파일(.zip)을 받습니다.", en: "Download the .zip with the button above." },
  "download.install.step2": { ko: "압축을 풉니다 — 별도 설치 프로그램은 없습니다.", en: "Unzip it — there's no separate installer to run." },
  "download.install.step3": {
    ko: "풀린 폴더 안의 실행 파일을 더블클릭하면 바로 시작됩니다 (macOS: AIsaac.app · Windows: start.bat · Linux: run.sh).",
    en: "Double-click the launcher inside the unzipped folder to start (macOS: AIsaac.app · Windows: start.bat · Linux: run.sh).",
  },
  "download.older.title": { ko: "이전 버전이 필요하신가요?", en: "Need an older version?" },
  "download.older.desc": {
    ko: "GitHub Releases에서 전체 버전 목록과 릴리즈 노트를 확인할 수 있습니다.",
    en: "Browse the full version history and release notes on GitHub Releases.",
  },
  "download.older.button": { ko: "GitHub에서 보기", en: "View on GitHub" },

  // Footer
  "footer.tagline": { ko: "골방의 질문을 논문으로. 혼자 하는 연구를 끝까지 함께 가는 AI 연구 어시스턴트, AIsaac.", en: "From a question in a small room to a finished paper. AIsaac, an AI research assistant that goes the whole way with research done alone." },
  "footer.rights": { ko: "모든 권리 보유.", en: "All rights reserved." },

  // App shell
  "app.nav.workspace": { ko: "연구 워크스페이스", en: "Workspace" },
  "app.nav.prism": { ko: "프리즘 분해", en: "Prism decomposition" },
  "app.nav.orbit": { ko: "궤도 처리", en: "Orbit processing" },
  "app.nav.archive": { ko: "지식 아카이브", en: "Archive" },
  "app.nav.settings": { ko: "설정", en: "Settings" },
  "app.back": { ko: "랜딩으로", en: "Back to site" },

  "app.header.title": { ko: "연구 콘솔", en: "Research console" },
  "app.header.subtitle": { ko: "아이디어를 궤도에 올리고 논문으로 완성합니다", en: "Put ideas into orbit and complete them as papers" },

  // Beam input
  "console.input.title": { ko: "백색광 입력", en: "White beam input" },
  "console.input.placeholder": {
    ko: "날것의 아이디어나 원시 데이터를 입력하세요. 예: '도시 열섬 효과와 야간 조도의 상관관계'",
    en: "Enter a raw idea or raw data. e.g. 'Correlation between urban heat islands and nighttime light levels'",
  },
  "console.input.button": { ko: "프리즘에 통과시키기", en: "Send through the prism" },
  "console.input.processing": { ko: "분해 중…", en: "Refracting…" },

  // Spectrum output
  "console.spectrum.title": { ko: "분해된 스펙트럼", en: "Decomposed spectrum" },
  "console.spectrum.empty": { ko: "위에 아이디어를 입력하면 스펙트럼이 여기에 나타납니다.", en: "Enter an idea above and its spectrum will appear here." },
  "console.spectrum.confidence": { ko: "신뢰도", en: "Confidence" },
  "console.spectrum.subject": { ko: "분해 대상", en: "Subject" },

  "band.violet.d": {
    ko: "가시광선 너머에서 포착한, 검증되지 않은 새로운 인과 가설입니다.",
    en: "An untested causal hypothesis captured beyond the visible band.",
  },
  "band.blue.d": {
    ko: "주장을 지탱하는 핵심 논증과 하위 명제의 논리 구조입니다.",
    en: "The logical scaffold of core arguments and sub-claims.",
  },
  "band.green.d": {
    ko: "관련 선행 연구와 인접 문헌을 자율적으로 수집했습니다.",
    en: "Relevant prior work and adjacent literature, gathered autonomously.",
  },
  "band.yellow.d": {
    ko: "데이터에서 반복적으로 관측되는 통계적 신호입니다.",
    en: "Statistical signals recurring in the underlying data.",
  },
  "band.red.d": {
    ko: "가설을 무너뜨릴 수 있는 잠재적 반증 지점입니다.",
    en: "Potential points that could falsify the hypothesis.",
  },

  // Pipeline stages
  "stage.done": { ko: "완료", en: "Done" },
  "stage.active": { ko: "진행", en: "Active" },
  "stage.queued": { ko: "대기", en: "Queued" },
  "band.hidden": { ko: "숨은 발견", en: "Hidden find" },

  // Orbit panel
  "console.orbit.title": { ko: "자율 공전 상태", en: "Autonomous orbit status" },
  "console.orbit.running": { ko: "공전 중", en: "Orbiting" },
  "console.orbit.idle": { ko: "대기", en: "Idle" },

  // Archive
  "console.archive.title": { ko: "지식 아카이브", en: "Knowledge archive" },
  "console.archive.desc": { ko: "완성된 논문과 리포트를 조회합니다.", en: "Browse completed papers and reports." },
  "console.archive.open": { ko: "열기", en: "Open" },
  "console.archive.phase": { ko: "위상", en: "Phase" },
  "console.archive.updated": { ko: "갱신", en: "Updated" },

  // Settings
  "settings.title": { ko: "설정", en: "Settings" },
  "settings.language.title": { ko: "언어", en: "Language" },
  "settings.language.desc": { ko: "인터페이스 문구 언어를 선택합니다.", en: "Choose the interface language." },
  "settings.theme.title": { ko: "관측 모드", en: "Observation mode" },
  "settings.theme.desc": { ko: "밝은 사이언스 모드와 달의 뒷면(다크) 모드를 전환합니다.", en: "Switch between light science mode and the dark side (dark) mode." },
  "settings.theme.light": { ko: "라이트", en: "Light" },
  "settings.theme.dark": { ko: "다크", en: "Dark" },

  "common.langToggle": { ko: "KO / EN", en: "KO / EN" },
} satisfies Record<string, Dict>

export type TKey = keyof typeof dict

type Ctx = {
  lang: Lang
  setLang: (l: Lang) => void
  toggle: () => void
  t: (key: TKey) => string
}

const LanguageContext = createContext<Ctx | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("ko")
  const toggle = () => setLang((p) => (p === "ko" ? "en" : "ko"))
  const t = (key: TKey) => dict[key][lang]
  return (
    <LanguageContext.Provider value={{ lang, setLang, toggle, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider")
  return ctx
}
