import { apiFetch, BACKEND_URL, ApiError } from './client'

export interface QueryChunk {
  trace?: string
  final?: boolean
  answer?: string
  comment?: string
}

// POST /query는 text/event-stream을 응답한다 — EventSource는 GET 전용이라 못 쓰고,
// fetch()의 ReadableStream을 직접 읽는다. 백엔드가 청크마다
// f"data: {json.dumps(chunk)}\n\n"로 보내므로(main.py 참고) "\n\n"로 잘라서
// "data: " 접두사가 붙은 줄만 JSON으로 파싱 — frontend/views/chat.py의 파싱 로직과 동일.
export async function* streamQuery(params: {
  prompt: string
  model: string
  effort: string
  threadId: string
}): AsyncGenerator<QueryChunk> {
  const res = await fetch(`${BACKEND_URL}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: params.prompt,
      model: params.model,
      effort: params.effort,
      thread_id: params.threadId,
    }),
  })
  if (!res.ok || !res.body) {
    throw new ApiError(res.status, res.statusText)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? '' // 마지막 조각은 아직 안 끝났을 수 있어 버퍼에 남긴다
    for (const event of events) {
      if (!event.startsWith('data: ')) continue
      yield JSON.parse(event.slice('data: '.length)) as QueryChunk
    }
  }
}

// 메시지 트리밍 2단계(08-13 후속, 수동 삭제) — 화면이 그리는 이력은 SSE로 받은 조각을
// 조립한 세션 로컬 state라 백엔드 체크포인트의 실제 메시지 id가 없다. 이 함수로 진짜
// 목록(id 포함)을 받아와야 "이 메시지를 지워줘"를 구체적인 id로 요청할 수 있다.
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export function getQueryMessages(threadId: string) {
  return apiFetch<{ messages: ChatMessage[] }>(`/query/${threadId}/messages`)
}

export function deleteQueryMessage(threadId: string, messageId: string) {
  return apiFetch<{ deleted_id: string }>(`/query/${threadId}/messages/${messageId}`, { method: 'DELETE' })
}

// 챗(④) 세션 목록 — api/research.ts의 세션 함수 3개와 같은 계약(main.py
// /api/chat/sessions 참고). 세션 "생성"은 /query가 첫 메시지에서 알아서 하므로
// 여긴 목록/제목수정/닫기만 있다.
export interface ChatSession {
  thread_id: string
  title: string
  created_at: string
  updated_at: string
}

export function listChatSessions() {
  return apiFetch<{ sessions: ChatSession[] }>('/chat/sessions')
}

export function renameChatSession(threadId: string, title: string) {
  return apiFetch(`/chat/sessions/${threadId}/title`, {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export function closeChatSession(threadId: string) {
  return apiFetch(`/chat/sessions/${threadId}`, { method: 'DELETE' })
}
