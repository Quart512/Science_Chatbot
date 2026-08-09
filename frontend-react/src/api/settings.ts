import { apiFetch } from './client'

export interface ApiKeyStatus {
  provider: 'gemini' | 'claude'
  saved: boolean
  masked_key: string | null
  updated_at: string | null
}

export function listApiKeyStatus() {
  return apiFetch<{ keys: ApiKeyStatus[] }>('/settings/keys')
}

export function saveApiKey(provider: 'gemini' | 'claude', apiKey: string) {
  return apiFetch<{ provider: string; action: string }>('/settings/keys', {
    method: 'POST',
    body: JSON.stringify({ provider, api_key: apiKey }),
  })
}

export function deleteApiKey(provider: 'gemini' | 'claude') {
  return apiFetch<{ provider: string; action: string }>(`/settings/keys/${provider}`, { method: 'DELETE' })
}

export interface VersionInfo {
  version: string
  release_notes: string | null
}

export function getVersion() {
  return apiFetch<VersionInfo>('/version')
}

// asked — "아직 동의를 물어본 적 없음"과 "물어봤는데 거부함"을 가르는 값(08-09).
// consent만으로는 둘이 구분되지 않아 거부한 사용자에게 첫 실행 안내창이 매번 다시 뜬다.
export interface TelemetryConsent {
  consent: boolean
  asked: boolean
}

export function getTelemetryConsent() {
  return apiFetch<TelemetryConsent>('/settings/telemetry')
}

export function setTelemetryConsent(consent: boolean) {
  return apiFetch<TelemetryConsent>('/settings/telemetry', {
    method: 'POST',
    body: JSON.stringify({ consent }),
  })
}

// 첫 실행 시 bge-m3(약 2.1GB) 준비 진행률(08-09, embeddings.py 참고). 검색·논문 기능이
// 이 준비를 기다리므로 화면이 상태를 알아야 한다 — 안 그러면 "질문했는데 한참 멈춤"으로만 보인다.
export interface EmbeddingStatus {
  state: 'idle' | 'downloading' | 'loading' | 'ready' | 'failed'
  downloaded_bytes: number
  total_bytes: number
  error: string | null
}

export function getEmbeddingStatus() {
  return apiFetch<EmbeddingStatus>('/embedding-status')
}

// 로컬 모델(Qwen-tuned) 선택 설치(08-09, local_model.py 참고). 배포판에 안 실리고
// 사용자가 받기를 누를 때만 내려받는다(약 1GB).
//   installed — GGUF와 llama-server가 **둘 다** 있는가(디스크로 매번 확인)
//   supported — 이 운영체제·CPU에 맞는 llama.cpp 빌드가 있는가
export interface LocalModelStatus {
  state: 'not_installed' | 'downloading' | 'ready' | 'failed'
  phase: string
  downloaded_bytes: number
  total_bytes: number
  error: string | null
  installed: boolean
  supported: boolean
}

export function getLocalModelStatus() {
  return apiFetch<LocalModelStatus>('/local-model')
}

export function installLocalModel() {
  return apiFetch<LocalModelStatus>('/local-model/install', { method: 'POST' })
}

export function deleteLocalModel() {
  return apiFetch<LocalModelStatus>('/local-model', { method: 'DELETE' })
}
