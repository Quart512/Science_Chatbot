import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { streamQuery } from '../api/chat'
import { getInterestDraft } from '../api/interests'
import './ChatPanel.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
  comment?: string
}

const MODELS = ['gemini', 'claude', 'Qwen-tuned'] as const
const EFFORTS = ['low', 'medium', 'high'] as const

// 셸에 항상 떠 있는 챗 패널(08-04 설계 노트 "React 전환" 참고) — 연구 워크플로우 등
// 다른 화면을 보면서 동시에 쓸 수 있게 하는 게 이 컴포넌트의 존재 이유. frontend/views/
// chat.py와 기능 동등(모델·effort 선택, 스트리밍, "관심사로 등록" 버튼).
export function ChatPanel() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(true)
  const [threadId] = useState(() => crypto.randomUUID())
  const [model, setModel] = useState<string>(MODELS[0])
  const [effort, setEffort] = useState<string>('medium')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [progress, setProgress] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [draftError, setDraftError] = useState('')

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
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: question }])
    setIsStreaming(true)
    setProgress('')

    let answer = ''
    let comment = ''
    try {
      for await (const chunk of streamQuery({ prompt: question, model, effort, threadId })) {
        if (chunk.trace) setProgress(chunk.trace)
        if (chunk.final) {
          answer = chunk.answer ?? ''
          comment = chunk.comment ?? ''
        }
      }
    } catch (e) {
      answer = `백엔드 호출 실패: ${(e as Error).message}`
    }

    setProgress('')
    setIsStreaming(false)
    setMessages((m) => [...m, { role: 'assistant', content: answer, comment }])
  }

  if (!open) {
    return (
      <button className="chat-panel-toggle" onClick={() => setOpen(true)}>
        💬 챗 열기
      </button>
    )
  }

  return (
    <aside className="chat-panel">
      <div className="chat-panel-header">
        <span>💬 챗</span>
        <button onClick={() => setOpen(false)} aria-label="챗 닫기">
          ✕
        </button>
      </div>

      <div className="chat-panel-controls">
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          {MODELS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <select value={effort} onChange={(e) => setEffort(e.target.value)}>
          {EFFORTS.map((e) => (
            <option key={e} value={e}>
              {e}
            </option>
          ))}
        </select>
      </div>
      <p className="chat-panel-thread-id">thread_id: {threadId}</p>
      <button className="chat-panel-register-interest" onClick={registerAsInterest}>
        💡 이 대화를 관심사로 등록
      </button>
      {draftError && <p className="chat-panel-error">{draftError}</p>}

      <div className="chat-panel-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-message chat-message-${m.role}`}>
            <div className="chat-message-content">{m.content}</div>
            {m.comment && <div className="chat-message-comment">💬 {m.comment}</div>}
          </div>
        ))}
        {isStreaming && <div className="chat-panel-progress">⏳ {progress || '진행 중...'}</div>}
      </div>

      <form
        className="chat-panel-input"
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="물리에 대해 궁금한 걸 물어보세요"
          disabled={isStreaming}
        />
        <button type="submit" disabled={isStreaming || !input.trim()}>
          전송
        </button>
      </form>
    </aside>
  )
}
