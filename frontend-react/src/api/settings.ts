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
