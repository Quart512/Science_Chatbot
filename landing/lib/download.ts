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
const REPO = "Quart512/Science_Chatbot"
const RELEASES_BASE = `https://github.com/${REPO}/releases/latest`

export const RELEASES_PAGE_URL = RELEASES_BASE
export const ASSET_URLS = {
  macos: `${RELEASES_BASE}/download/AIsaac-macos.zip`,
  windows: `${RELEASES_BASE}/download/AIsaac-windows.zip`,
  linux: `${RELEASES_BASE}/download/AIsaac-linux.zip`,
  docker: `${RELEASES_BASE}/download/AIsaac-docker.zip`,
} as const

export type Platform = keyof typeof ASSET_URLS | null

function detectPlatform(): Platform {
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
export function useDownloadUrl(): { url: string; platform: Platform } {
  const [platform, setPlatform] = useState<Platform>(null)

  useEffect(() => {
    setPlatform(detectPlatform())
  }, [])

  return { url: platform ? ASSET_URLS[platform] : RELEASES_PAGE_URL, platform }
}
