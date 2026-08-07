"use client"

import { useEffect, useState } from "react"

// GitHub Releases 다운로드 링크 — RoadMap "[배포] 배포 자동화" 항목의 release.yml이
// 태그(v*) push마다 AIsaac-macos.zip / AIsaac-windows.zip / AIsaac-linux.zip /
// AIsaac-docker.zip 4개를 올린다. releases/latest/download/<asset> 경로는 GitHub이
// 항상 최신 릴리즈로 리다이렉트해주므로 버전 번호를 하드코딩할 필요가 없다.
//
// 주의(08-06) — 이 저장소는 아직 실제 v* 태그를 push한 적이 없다(사용자 승인 뒤
// 별도 진행 예정, RoadMap 참고). 그 전까지는 이 링크들이 404다 — 코드가 아니라
// 릴리즈 프로세스가 아직 안 끝난 것뿐이라, 첫 태그가 올라가는 순간 그대로 동작한다.
//
// 08-07 — 저장소 이름이 Science_Chatbot → AIsaac으로 바뀌어 갱신. GitHub이 옛
// URL(Quart512/Science_Chatbot)을 당분간 새 이름으로 리다이렉트해주지만, 리다이렉트에
// 기대지 않고 실제 이름으로 못박는다.
const REPO = "Quart512/AIsaac"
const RELEASES_BASE = `https://github.com/${REPO}/releases/latest`

export const REPO_URL = `https://github.com/${REPO}`
export const RELEASES_PAGE_URL = RELEASES_BASE
export const ASSET_URLS = {
  macos: `${RELEASES_BASE}/download/AIsaac-macos.zip`,
  windows: `${RELEASES_BASE}/download/AIsaac-windows.zip`,
  linux: `${RELEASES_BASE}/download/AIsaac-linux.zip`,
  docker: `${RELEASES_BASE}/download/AIsaac-docker.zip`,
} as const

export type Platform = keyof typeof ASSET_URLS | null

// detectPlatform()은 User-Agent로 OS만 가른다 — "docker"는 감지 대상이 아니라
// PLATFORMS(아래, 전체 4종 카드용) 쪽에만 있는 값이라 Platform과 분리해둔다.
// 이렇게 좁혀야 다운로드 페이지의 "감지된 OS" 분기에서 docker 케이스를 안 다뤄도
// 타입 에러가 안 난다(실제로 나올 수 없는 값이니 다뤄야 할 이유도 없다).
export type DetectedPlatform = Exclude<Platform, "docker">

// 08-07 — 08-05 실측으로 확정된 제약(RoadMap "portable 파이썬 번들" 항목):
// onnxruntime이 macOS x86_64용 wheel을 이 프로젝트가 요구하는 파이썬 버전에서
// 아예 안 만들어 Intel Mac은 portable 번들 경로 자체가 원리적으로 막혀 있다.
// Windows·Linux 빌드도 각각 windows-latest/ubuntu-latest(둘 다 x86_64) 러너에서만
// 빌드돼 그 아키텍처 전용이다 — 다운로드 페이지가 이 셋을 있는 그대로 적어야
// 사용자가 못 도는 파일을 받는 사고를 막는다("조용히 자르지 말고 정직하게 실패").
export const PLATFORMS: {
  id: keyof typeof ASSET_URLS
  labelKey: string
  archKey: string
  url: string
}[] = [
  { id: "macos", labelKey: "download.platform.macos", archKey: "download.arch.macos", url: ASSET_URLS.macos },
  { id: "windows", labelKey: "download.platform.windows", archKey: "download.arch.windows", url: ASSET_URLS.windows },
  { id: "linux", labelKey: "download.platform.linux", archKey: "download.arch.linux", url: ASSET_URLS.linux },
  { id: "docker", labelKey: "download.platform.docker", archKey: "download.arch.docker", url: ASSET_URLS.docker },
]

function detectPlatform(): DetectedPlatform {
  if (typeof navigator === "undefined") return null
  const ua = navigator.userAgent
  if (/Mac/i.test(ua)) return "macos"
  if (/Win/i.test(ua)) return "windows"
  if (/Linux/i.test(ua)) return "linux"
  return null
}

// 서버 렌더링 시점엔 navigator가 없어 항상 null(= 전체 릴리즈 페이지로 폴백)로
// 시작하고, 마운트 후 실제 브라우저 UA로 갱신한다 — SSR/클라이언트 마크업이
// 갈리는 hydration 경고를 피하기 위해 초기값을 고정해두는 흔한 패턴.
export function useDownloadUrl(): { url: string; platform: DetectedPlatform } {
  const [platform, setPlatform] = useState<DetectedPlatform>(null)

  useEffect(() => {
    setPlatform(detectPlatform())
  }, [])

  return { url: platform ? ASSET_URLS[platform] : RELEASES_PAGE_URL, platform }
}

// 08-07 — Intel Mac 사용자에게 최선의 노력으로 경고를 준다. navigator.userAgent엔
// 더 이상 실제 CPU 아키텍처가 안 실려있어(브라우저들이 프라이버시 목적으로
// 축소함) UA만으론 Apple Silicon/Intel을 못 가른다. Client Hints의
// navigator.userAgentData.getHighEntropyValues(['architecture'])가 유일한 방법인데
// Chromium 계열에만 있고 Safari·Firefox는 아예 없다 — 그래서 "확실히 Intel Mac"일
// 때만 true, 그 외(감지 불가 포함)는 전부 null로 반환한다. 이 값에만 기대지 않고
// 페이지에는 정적 안내문도 항상 같이 둔다(감지가 안 되는 브라우저가 더 많아서).
export function useIsLikelyIntelMac(): boolean | null {
  const [result, setResult] = useState<boolean | null>(null)

  useEffect(() => {
    const uaData = (navigator as unknown as { userAgentData?: { getHighEntropyValues?: (hints: string[]) => Promise<{ platform?: string; architecture?: string }> } }).userAgentData
    if (!uaData?.getHighEntropyValues) return
    uaData
      .getHighEntropyValues(["architecture"])
      .then((v) => {
        if (v.platform === "macOS" && v.architecture === "x86") setResult(true)
      })
      .catch(() => {})
  }, [])

  return result
}
