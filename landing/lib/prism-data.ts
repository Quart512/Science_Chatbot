import type { TKey } from "@/lib/i18n"

export type Band = {
  key: string
  labelKey: TKey
  descKey: TKey
  colorVar: string
  confidence: number
  hidden?: boolean
}

// The five refracted bands the prism produces from a white beam.
export const bands: Band[] = [
  {
    key: "violet",
    labelKey: "prism.band.violet",
    descKey: "band.violet.d",
    colorVar: "var(--spectrum-violet)",
    confidence: 61,
    hidden: true,
  },
  {
    key: "blue",
    labelKey: "prism.band.blue",
    descKey: "band.blue.d",
    colorVar: "var(--spectrum-blue)",
    confidence: 88,
  },
  {
    key: "green",
    labelKey: "prism.band.green",
    descKey: "band.green.d",
    colorVar: "var(--spectrum-green)",
    confidence: 79,
  },
  {
    key: "yellow",
    labelKey: "prism.band.yellow",
    descKey: "band.yellow.d",
    colorVar: "var(--spectrum-yellow)",
    confidence: 72,
  },
  {
    key: "red",
    labelKey: "prism.band.red",
    descKey: "band.red.d",
    colorVar: "var(--spectrum-red)",
    confidence: 54,
    hidden: true,
  },
]

export type Stage = {
  key: string
  labelKey: TKey
  status: "done" | "active" | "queued"
}

export const stages: Stage[] = [
  { key: "collect", labelKey: "orbit.node.1", status: "done" },
  { key: "analyze", labelKey: "orbit.node.2", status: "active" },
  { key: "synthesize", labelKey: "orbit.node.3", status: "queued" },
  { key: "verify", labelKey: "orbit.node.4", status: "queued" },
]

export type ArchiveItem = {
  id: string
  titleKo: string
  titleEn: string
  phase: 1 | 2 | 3 | 4
  updated: string
}

export const archive: ArchiveItem[] = [
  {
    id: "AIS-0421",
    titleKo: "도시 열섬과 야간 조도의 비선형 상관",
    titleEn: "Nonlinear coupling of urban heat islands and nighttime light",
    phase: 4,
    updated: "2026-07-28",
  },
  {
    id: "AIS-0417",
    titleKo: "해마 신경 발화의 위상 잠금 패턴",
    titleEn: "Phase-locking patterns in hippocampal firing",
    phase: 3,
    updated: "2026-07-30",
  },
  {
    id: "AIS-0410",
    titleKo: "심해 열수구 미생물의 대사 네트워크",
    titleEn: "Metabolic networks of deep-sea vent microbes",
    phase: 2,
    updated: "2026-08-01",
  },
  {
    id: "AIS-0402",
    titleKo: "외계 행성 대기의 스펙트럼 이상치",
    titleEn: "Spectral anomalies in exoplanet atmospheres",
    phase: 1,
    updated: "2026-08-03",
  },
]
