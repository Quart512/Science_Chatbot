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
  "hero.title.a": { ko: "뉴턴처럼 분해하고,", en: "Decompose like Newton," },
  "hero.title.b": { ko: "스스로 진실을 포착하다.", en: "capture the truth on its own." },
  "hero.desc": {
    ko: "AIsaac은 혼돈스러운 날것의 아이디어를 완벽한 지식의 스펙트럼으로 전환합니다. 아이디어 입력부터 논문 완성까지, 고독한 연구자의 호기심을 자율적으로 궤도에 올립니다.",
    en: "AIsaac turns raw, chaotic ideas into a complete spectrum of knowledge. From a single idea to a finished paper, it puts a lonely researcher's curiosity into a self-sustaining orbit.",
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
  "prism.desc": {
    ko: "입력된 아이디어를 뉴턴의 프리즘처럼 체계적인 논리 구조로 분해합니다. 가시광선 너머 적외선·자외선처럼, 인간의 눈에 보이지 않던 데이터 사이의 숨은 인과관계를 스스로 포착합니다.",
    en: "Each idea is refracted into a systematic logical structure, just as Newton's prism split light. Beyond the visible band—like infrared and ultraviolet—AIsaac captures the hidden causal links no human eye could see.",
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
  "orbit.desc": {
    ko: "매번 명령을 내리지 않아도, 수집·분석·정리 프로세스가 중심 아이디어를 축으로 스스로 공전합니다. 파편화된 자료와 실험 데이터를 강력한 중력으로 끌어당겨 단절 없는 연구 루프를 완성합니다.",
    en: "Without step-by-step commands, the collect–analyze–synthesize process orbits your core idea on its own. Fragmented references and experiment data are pulled in by gravity into one unbroken research loop.",
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
  "dark.desc": {
    ko: "지구에서 관측할 수 없는 달의 뒷면처럼, 아무도 알아주지 않는 골방에서 길을 잃은 연구자의 미제 질문을 탐사합니다. 축적된 결과물은 차오르는 보름달처럼 정돈된 학술 논문으로 세상 밖에 쏘아 올려집니다.",
    en: "Like the far side of the moon that Earth never sees, AIsaac explores the unsolved questions of researchers lost in unseen rooms. What it gathers rises—like a moon waxing to full—into a polished paper launched back into the light.",
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

  // Footer
  "footer.tagline": { ko: "인간의 눈에 보이지 않는 지식을 궤도 위에 올리는 자율형 연구 프리즘.", en: "An autonomous research prism that puts invisible knowledge into orbit." },
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
