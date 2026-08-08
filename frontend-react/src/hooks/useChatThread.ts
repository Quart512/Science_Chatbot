import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { streamQuery, getQueryMessages, deleteQueryMessage } from '../api/chat'
import type { ChatMessage, TraceStep } from '../api/chat'
import { getInterestDraft } from '../api/interests'

export interface ChatUIMessage {
  id?: string // 스트리밍 중인 임시 버블(사용자 입력·진행 중 답변)엔 아직 없음
  role: 'user' | 'assistant'
  content: string
  comment?: string
  trace?: TraceStep[]
}

// 서버가 돌려주는 ChatMessage(comment/trace가 string|null)를 화면 표시용
// ChatUIMessage(전부 optional)로 변환 — null은 "값 없음"을 optional 필드 생략으로 표현.
function fromServerMessage(m: ChatMessage): ChatUIMessage {
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    comment: m.comment ?? undefined,
    trace: m.trace ?? undefined,
  }
}

export const CHAT_MODELS = ['gemini', 'claude', 'Qwen-tuned'] as const
export const CHAT_EFFORTS = ['low', 'medium', 'high'] as const

// 화면에서 "질문 하나 + 그 답변"을 한 블록으로 묶어 보여주기 위한 그룹핑(사용자 요청 —
// user/assistant는 색으로 구분되지만 turn 사이 구분이 안 갔음). messages는 항상
// user로 시작해 user/assistant가 번갈아 온다(useChatThread가 보내는 순서·서버
// 체크포인트 순서 둘 다) — user를 만날 때마다 새 turn을 열고, 그 외(assistant, 또는
// 첫 메시지부터 assistant인 예외적인 경우)는 직전 turn에 이어붙인다.
export function groupMessagesIntoTurns(messages: ChatUIMessage[]): ChatUIMessage[][] {
  const turns: ChatUIMessage[][] = []
  for (const m of messages) {
    if (m.role === 'user' || turns.length === 0) {
      turns.push([m])
    } else {
      turns[turns.length - 1].push(m)
    }
  }
  return turns
}

// 챗 스레드 하나의 상태·전송 로직 — 원래 ChatPanel.tsx 하나에만 있던 걸 뽑았다.
// 화면 개선 ⑤로 이 로직이 왼쪽 독립 화면(Chat.tsx)과 오른쪽 상시 패널(ChatPanel.tsx)
// 두 곳에서 동시에 필요해진 시점이라 훅으로 분리 — 미리 예상해서 뽑은 게 아니라
// 두 번째 호출부가 실제로 생기는 지금 뽑는 것(RoadMap "단순 경로부터" 원칙).
//
// hydrateOnMount=true면 마운트 시 getQueryMessages로 과거 이력을 불러온다(왼쪽 화면이
// 세션 목록에서 과거 대화를 열 때 필요). false면(오른쪽 패널의 "새 대화" 진입 등)
// 빈 상태로 시작 — threadId가 아직 chat_sessions에 없을 수도 있는데, 이때
// getQueryMessages를 불러도 에러는 아니다(체크포인트가 없으면 서버가 빈 배열을
// 돌려줌, main.py 주석 참고)라서 사실 항상 켜둬도 안전하지만, 매번 빈 요청을
// 날리지 않으려고 옵션으로 남긴다.
export function useChatThread(threadId: string, options?: { hydrateOnMount?: boolean; onFirstMessageSent?: () => void }) {
  const hydrateOnMount = options?.hydrateOnMount ?? false
  const onFirstMessageSent = options?.onFirstMessageSent
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [model, setModel] = useState<string>(CHAT_MODELS[0])
  const [effort, setEffort] = useState<string>('medium')
  const [messages, setMessages] = useState<ChatUIMessage[]>([])
  const [input, setInput] = useState('')
  const [progress, setProgress] = useState<TraceStep[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [draftError, setDraftError] = useState('')
  const hasSentRef = useRef(false)

  useEffect(() => {
    hasSentRef.current = false
    setMessages([])
    if (!hydrateOnMount) return
    getQueryMessages(threadId)
      .then(({ messages: fromServer }) => {
        setMessages(fromServer.map(fromServerMessage))
        if (fromServer.length > 0) hasSentRef.current = true
      })
      .catch(() => {
        // 새 thread_id(아직 체크포인트 없음)면 조회가 의미 없으니 조용히 빈 상태 유지
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, hydrateOnMount])

  async function registerAsInterest() {
    setDraftError('')
    try {
      const draft = await getInterestDraft(threadId)
      navigate('/interests', { state: draft })
    } catch (e) {
      setDraftError(`초안 생성 실패: ${(e as Error).message}`)
    }
  }

  async function send() {
    const question = input.trim()
    if (!question || isStreaming) return
    const isFirstMessage = !hasSentRef.current
    hasSentRef.current = true
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: question }])
    setIsStreaming(true)
    setProgress([])

    let answer = ''
    let comment = ''
    let trace: TraceStep[] = []
    let succeeded = true
    try {
      for await (const chunk of streamQuery({ prompt: question, model, effort, threadId })) {
        if (chunk.trace) {
          trace = chunk.trace
          setProgress(chunk.trace)
        }
        // 08-08 — 백엔드가 본문으로 보낸 에러(main.py /api/query 참고). 여기서 안 잡으면
        // 빈 스트림으로 끝나 succeeded=true가 되고, 아래 성공 경로가 체크포인트 목록으로
        // 화면을 통째로 교체하면서 **방금 친 질문까지 사라진다**(v0.1.0에서 실제로 겪음).
        if (chunk.error) {
          succeeded = false
          answer = chunk.error
          break
        }
        if (chunk.final) {
          answer = chunk.answer ?? ''
          comment = chunk.comment ?? ''
        }
      }
      // 에러도 아니고 답변도 못 받은 채 스트림이 끝난 경우 — 서버가 죽었거나 연결이
      // 끊긴 상황이다. 이때도 성공으로 두면 위와 같은 "질문이 사라지는" 증상이 난다.
      if (succeeded && !answer) {
        succeeded = false
        answer = '답변을 받지 못했습니다. 연결이 끊겼거나 서버가 응답하지 않았습니다.'
      }
    } catch (e) {
      succeeded = false
      answer = `백엔드 호출 실패: ${(e as Error).message}`
    }

    setProgress([])
    setIsStreaming(false)

    // 08-08 — 세션 목록 갱신은 성공/실패와 무관하게 한다. 백엔드는 **스트리밍을 시작하기
    // 전에** chat_sessions 행을 만들므로(main.py /api/query), 답변이 실패해도 세션 자체는
    // 이미 존재한다. 예전엔 이 줄이 성공 경로 안에만 있어서, 실패하면 왼쪽 사이드바에
    // 새 대화가 안 나타났다(v0.1.1 실사용에서 실제로 겪음 — 답변은 실패했는데 세션이
    // 사라진 것처럼 보였다).
    queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })

    if (succeeded) {
      // 실제 체크포인트 목록으로 교체해 메시지별 id를 확보한다(메시지 삭제에 필요 —
      // 08-13 메시지 트리밍 2단계). comment·trace(08-07)는 이제 final_answer가
      // AIMessage.additional_kwargs에 심어 체크포인트에 남기므로, 서버가 돌려주는 값을
      // 그대로 쓰면 된다(예전엔 체크포인트에 없다고 보고 방금 받은 값을 수동으로
      // 마지막 메시지에 덧붙였는데, 그 전제가 틀렸었다 — 위 main.py 변경 참고).
      try {
        const { messages: fromServer } = await getQueryMessages(threadId)
        setMessages(fromServer.map(fromServerMessage))
        // 새 스레드(왼쪽 화면에서 방금 시작한 대화)라면 URL을 이 thread_id로 옮긴다 —
        // 백엔드가 이미 이 시점에 chat_sessions 행과 체크포인트를 둘 다 갖고 있으므로
        // (스트리밍 시작 전에 lazy 생성, main.py 참고) 이동한 뒤 재조회해도 빈 화면이
        // 안 뜬다. 스트림 도중에 미리 옮기면(체크포인트가 아직 안 채워진 시점) 오히려
        // 화면이 잠깐 비어 보이므로 일부러 성공 후로 미뤘다.
        if (isFirstMessage) onFirstMessageSent?.()
        return
      } catch {
        // 목록 재조회 실패해도 방금 받은 답변은 화면에 보여야 하므로 아래로 폴백
      }
    }
    setMessages((m) => [...m, { role: 'assistant', content: answer, comment, trace }])
  }

  async function deleteMessage(id: string) {
    await deleteQueryMessage(threadId, id)
    setMessages((m) => m.filter((msg) => msg.id !== id))
  }

  return {
    model, setModel,
    effort, setEffort,
    messages,
    input, setInput,
    progress,
    isStreaming,
    draftError,
    send,
    deleteMessage,
    registerAsInterest,
  }
}
