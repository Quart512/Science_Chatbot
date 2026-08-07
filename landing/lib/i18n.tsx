"use client"

import { createContext, useContext, useState, type ReactNode } from "react"

export type Lang = "ko" | "en"

type Dict = Record<Lang, string>

// Every UI string is defined for both languages.
export const dict = {
  // Nav
  "nav.prism": { ko: "프리즘", en: "Prism" },
  "nav.orbit": { ko: "위성 궤도", en: "Orbit" },
  "nav.darkside": { ko: "달의 뒷면", en: "Dark Side" },
  "nav.archive": { ko: "아카이브", en: "Archive" },
  "nav.launch": { ko: "다운로드", en: "Download" },

  // Hero
  // 08-06 — "가동 중"/"online"은 상시 접속 가능한 호스팅 서비스처럼 읽히는데
  // AIsaac은 사용자가 내려받아 자기 컴퓨터에서 돌리는 로컬 앱이라 사실과 다르다
  // (텔레메트리 자체를 안 보낸다는 RoadMap 로깅 설계 노트와 같은 이유 — "가동 중"을
  // 판단할 서버가 없다). 실제 배포 형태를 그대로 적는다.
  "hero.status": { ko: "자율형 연구 프리즘 · 로컬 실행", en: "Autonomous research prism · runs locally" },
  // 08-07 — "뉴턴처럼 분해하고, 스스로 진실을 포착하다"는 v0.app이 임의로 지은
  // 문구였다(사용자 피드백 — 원래 병합 지시는 "슬로건은 1(제미나이 브랜드 초안)을
  // 병합"이었는데 이 부분만 안 지켜져 있었음). RoadMap 부록 "1. 제미나이가 작성한
  // 브랜드/README 초안"의 실제 승인된 메인 슬로건("AIsaac / Analyze. Discover.
  // Orbit. / Turning the dark side of knowledge into a perfect scientific
  // orbit.")으로 교체 — 세 동사(Analyze/Discover/Orbit)는 브랜드 고정 문구라 언어
  // 무관하게 영어 그대로 두고, 그 아래 서브라인만 KO/EN 각각 번역해 둔다.
  "hero.title.a": { ko: "Analyze. Discover. Orbit.", en: "Analyze. Discover. Orbit." },
  "hero.title.b": {
    ko: "지식의 어두운 이면을, 완벽한 과학의 궤도로.",
    en: "Turning the dark side of knowledge into a perfect scientific orbit.",
  },
  // 08-07 — "혼돈스러운 날것의 아이디어를 완벽한 지식의 스펙트럼으로 전환합니다"
  // 같은 표현이 알아듣기 힘들다는 지적 — 프리즘 은유를 문장 안에 욱여넣지 않고,
  // 실제로 무엇을 하는 서비스인지 평서문으로 먼저 말한다(제미나이 초안의 소개
  // 문단을 뼈대로 축약).
  "hero.desc": {
    ko: "AIsaac은 아이디어를 논문으로 완성하는 전 과정을 자율적으로 돕는 AI 연구 어시스턴트입니다. 골방에서 혼자 연구하는 대학원생부터 취미로 파고드는 아마추어 과학자까지 — 막연한 호기심을 끝까지 밀고 나가 완결된 지식으로 만들어 드립니다.",
    en: "AIsaac is an AI research assistant that autonomously carries an idea all the way to a finished paper. From graduate students working alone to hobbyists chasing a hunch, it turns a stray question into complete knowledge.",
  },
  "hero.cta.primary": { ko: "다운로드", en: "Download" },
  "hero.cta.secondary": { ko: "궤도 살펴보기", en: "Explore the orbit" },
  // 08-06 — 원래 가짜 사용량 숫자(10,482 등)였다. AIsaac은 텔레메트리를 안 보내
  // 원리적으로 실사용 통계를 낼 방법이 없어서(로깅 설계 노트 참고) 지어낸 숫자
  // 대신 실제로 참인 특징 3가지로 바꿨다.
  "hero.metric.1.label": { ko: "실행 방식", en: "Runs" },
  "hero.metric.1.value": { ko: "100% 로컬", en: "100% local" },
  "hero.metric.2.label": { ko: "지원 플랫폼", en: "Platforms" },
  "hero.metric.2.value": { ko: "macOS·Win·Linux", en: "macOS·Win·Linux" },
  "hero.metric.3.label": { ko: "데이터 저장 위치", en: "Your data" },
  "hero.metric.3.value": { ko: "내 컴퓨터에만", en: "Stays on-device" },

  // Prism section
  "prism.kicker": { ko: "01 — 프리즘", en: "01 — Prism" },
  "prism.title": { ko: "분해와 발견", en: "Analyze & discover" },
  // 08-07 — "인간의 눈에 보이지 않던 데이터 사이의 숨은 인과관계를 스스로
  // 포착합니다" 같은 무주어·명사 나열형 문장을 "AIsaac이 ~합니다"로 주어를 살려
  // 고침(전반적 재작성 지적 반영).
  "prism.desc": {
    ko: "입력한 아이디어를 뉴턴의 프리즘처럼 체계적인 논리 구조로 분해합니다. 가시광선 너머의 적외선·자외선을 보듯, 사람 눈에는 안 보이던 데이터 사이의 숨은 인과관계까지 AIsaac이 직접 찾아냅니다.",
    en: "Each idea is refracted into a systematic logical structure, just as Newton's prism split light. Beyond the visible band—like infrared and ultraviolet—AIsaac finds the hidden causal links a human eye would miss.",
  },
  "prism.beam.label": { ko: "백색광 입력", en: "White beam in" },
  "prism.band.violet": { ko: "숨은 가설", en: "Hidden hypothesis" },
  "prism.band.blue": { ko: "논리 구조", en: "Logical structure" },
  "prism.band.green": { ko: "선행 연구", en: "Prior work" },
  "prism.band.yellow": { ko: "데이터 신호", en: "Data signal" },
  "prism.band.red": { ko: "반증 지점", en: "Falsification point" },

  // Orbit section
  "orbit.kicker": { ko: "02 — 위성 궤도", en: "02 — Orbit" },
  "orbit.title": { ko: "자율적 공전", en: "Autonomy" },
  // 08-07 — "프로세스가 중심 아이디어를 축으로 스스로 공전합니다"처럼 프로세스가
  // 문장의 주어가 되는 구조가 실제로 뭐가 자동화되는지 읽기 어렵다는 지적 —
  // "AIsaac이 ~한다"로 다시 씀.
  "orbit.desc": {
    ko: "매번 명령을 내리지 않아도 됩니다. 자료 수집부터 분석, 정리까지 — AIsaac이 중심 아이디어를 축으로 삼아 스스로 진행합니다. 흩어진 자료와 실험 데이터를 끌어모아 끊기지 않는 하나의 연구 흐름으로 이어줍니다.",
    en: "You don't need to give step-by-step commands. AIsaac collects, analyzes, and organizes around your core idea on its own — pulling in scattered references and experiment data to keep one unbroken research loop running.",
  },
  "orbit.node.1": { ko: "자료 수집", en: "Collect" },
  "orbit.node.2": { ko: "분석", en: "Analyze" },
  "orbit.node.3": { ko: "정리", en: "Synthesize" },
  "orbit.node.4": { ko: "검증", en: "Verify" },
  "orbit.core": { ko: "중심 아이디어", en: "Core idea" },
  "orbit.loop": { ko: "End-to-End 자율 루프", en: "End-to-end autonomous loop" },

  // Dark side section
  "dark.kicker": { ko: "03 — 달의 뒷면", en: "03 — Dark Side" },
  "dark.title": { ko: "골방의 미스테리", en: "The hidden mystery" },
  // 08-07 — 은유 두 개(달의 뒷면 + 차오르는 보름달)가 한 문장 안에 겹쳐 있어
  // 무슨 뜻인지 바로 안 들어온다는 지적 — 문장을 둘로 쪼개 "질문 → AIsaac이
  // 파고듦 → 논문으로 완성" 순서를 그대로 따라가게 함.
  "dark.desc": {
    ko: "지구에서는 볼 수 없는 달의 뒷면처럼, 아무도 몰라주는 골방에서 혼자 붙잡고 있던 질문들이 있습니다. AIsaac은 그 질문을 끝까지 파고들어, 보름달이 차오르듯 완성된 논문으로 세상에 내놓습니다.",
    en: "Like the far side of the moon that Earth never sees, there are questions researchers hold onto alone, unseen by anyone. AIsaac digs into them until they rise—like a moon waxing to full—into a finished paper.",
  },
  "dark.phase.1": { ko: "미제 질문", en: "Open question" },
  "dark.phase.2": { ko: "탐사 중", en: "Exploring" },
  "dark.phase.3": { ko: "초안 응축", en: "Drafting" },
  "dark.phase.4": { ko: "완성 논문", en: "Full paper" },

  // CTA
  "cta.title": { ko: "당신의 백색광을 스펙트럼으로.", en: "Turn your white beam into a spectrum." },
  "cta.desc": {
    ko: "지금 아이디어 하나를 궤도에 올려보세요. AIsaac이 나머지를 공전시킵니다.",
    en: "Put one idea into orbit today. AIsaac will keep it revolving.",
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
  "footer.tagline": { ko: "사람 눈에 안 보이던 지식을 찾아 궤도에 올리는 자율형 연구 프리즘, AIsaac.", en: "An autonomous research prism that finds invisible knowledge and puts it into orbit." },
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
