import { BACKEND_URL, ApiError } from './client'

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
  const res = await fetch(`${BACKEND_URL}/query`, {
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
