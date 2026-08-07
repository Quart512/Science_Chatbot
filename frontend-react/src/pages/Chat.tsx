import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CHAT_MODELS, CHAT_EFFORTS, groupMessagesIntoTurns, useChatThread } from '../hooks/useChatThread'
import { ChatIcon } from '../components/NavIcons'
import { StreamProgress } from '../components/StreamProgress'
import './Chat.css'

// 챗봇(④) 왼쪽 독립 화면 — 화면 개선 ⑤. Research.tsx와 같은 뼈대: threadId는
// URL(`/chat/:threadId`) 기준이라 새로고침해도 안 날아가고, 없으면 이 마운트에서
// 새로 uuid를 발급해 "새 대화" 상태로 시작한다(NewResearchForm과 달리 별도 시작
// 폼이 없는 이유는 챗엔 미리 정할 topic이 없기 때문 — 첫 메시지 자체가 시작 신호).
// 실제 스트리밍·이력 로직은 useChatThread 훅(오른쪽 ChatPanel과 공유)에 있다.
export function Chat() {
  const { threadId: urlThreadId } = useParams<{ threadId?: string }>()
  const navigate = useNavigate()
  const [freshThreadId] = useState(() => crypto.randomUUID())
  const threadId = urlThreadId ?? freshThreadId

  const chat = useChatThread(threadId, {
    hydrateOnMount: urlThreadId !== undefined,
    onFirstMessageSent: () => {
      if (!urlThreadId) navigate(`/chat/${threadId}`, { replace: true })
    },
  })

  return (
    <div className="chat-page">
      <div className="chat-page-header">
        <h1><ChatIcon size={22} /> 챗</h1>
        <div className="chat-page-controls">
          <select value={chat.model} onChange={(e) => chat.setModel(e.target.value)}>
            {CHAT_MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select value={chat.effort} onChange={(e) => chat.setEffort(e.target.value)}>
            {CHAT_EFFORTS.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button className="chat-page-register-interest" onClick={chat.registerAsInterest}>
        💡 이 대화를 관심사로 등록
      </button>
      {chat.draftError && <p className="chat-page-error">{chat.draftError}</p>}

      <div className="chat-page-messages">
        {chat.messages.length === 0 && !chat.isStreaming && (
          <p className="chat-page-empty">물리에 대해 궁금한 걸 물어보세요.</p>
        )}
        {groupMessagesIntoTurns(chat.messages).map((turn, ti) => (
          <div className="chat-turn" key={turn[0].id ?? `turn-${ti}`}>
            {turn.map((m, i) => (
              <div key={m.id ?? i} className={`chat-message chat-message-${m.role}`}>
                <div className="chat-message-content">{m.content}</div>
                {m.comment && <div className="chat-message-comment">💬 {m.comment}</div>}
                {m.trace && m.trace.length > 0 && <StreamProgress steps={m.trace} live={false} />}
                {m.id && (
                  <button
                    type="button"
                    className="chat-message-delete"
                    title="이 메시지 삭제"
                    onClick={() => chat.deleteMessage(m.id!)}
                  >
                    🗑
                  </button>
                )}
              </div>
            ))}
          </div>
        ))}
        {chat.isStreaming && <StreamProgress steps={chat.progress} />}
      </div>

      <form
        className="chat-page-input"
        onSubmit={(e) => {
          e.preventDefault()
          chat.send()
        }}
      >
        <input
          value={chat.input}
          onChange={(e) => chat.setInput(e.target.value)}
          placeholder="물리에 대해 궁금한 걸 물어보세요"
          disabled={chat.isStreaming}
        />
        <button type="submit" disabled={chat.isStreaming || !chat.input.trim()}>
          전송
        </button>
      </form>
    </div>
  )
}
