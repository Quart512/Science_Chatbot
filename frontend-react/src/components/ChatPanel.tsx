import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listChatSessions } from '../api/chat'
import { CHAT_MODELS, CHAT_EFFORTS, useChatThread } from '../hooks/useChatThread'
import './ChatPanel.css'

// 셸에 항상 떠 있는 챗 패널(08-04 설계 노트 "React 전환" 참고) — 연구 워크플로우 등
// 다른 화면을 보면서 동시에 쓸 수 있게 하는 게 이 컴포넌트의 존재 이유.
//
// 화면 개선 ⑤(08-06) 갱신 — 예전엔 마운트마다 crypto.randomUUID()로 새 thread_id를
// 발급해서 새로고침하면 대화가 사라졌다. 이제 chat_sessions 중 가장 최근(updated_at)
// 세션을 이어서 연다 — 왼쪽 독립 챗 화면(Chat.tsx)이 세션 여러 개를 관리하는 "허브"고,
// 여긴 그중 방금 쓰던 것 하나만 항상 보여주는 "바로가기"라는 역할 분담. 세션이 하나도
// 없을 때만(첫 사용) 새 uuid로 새 대화를 시작한다. 두 화면이 같은 react-query 키
// ('chat-sessions')를 보므로, 왼쪽에서 다른 세션에 메시지를 보내 그게 최신이 되면
// 이 패널도 자동으로 그 세션을 따라간다(전송 후 invalidateQueries는 useChatThread
// 안에서 처리).
export function ChatPanel() {
  const [open, setOpen] = useState(true)
  const [freshThreadId] = useState(() => crypto.randomUUID())
  const sessionsQuery = useQuery({ queryKey: ['chat-sessions'], queryFn: listChatSessions })
  const mostRecent = sessionsQuery.data?.sessions[0]
  const threadId = mostRecent?.thread_id ?? freshThreadId

  const chat = useChatThread(threadId, { hydrateOnMount: mostRecent !== undefined })

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
      <p className="chat-panel-thread-id">thread_id: {threadId}</p>
      <button className="chat-panel-register-interest" onClick={chat.registerAsInterest}>
        💡 이 대화를 관심사로 등록
      </button>
      {chat.draftError && <p className="chat-panel-error">{chat.draftError}</p>}

      <div className="chat-panel-messages">
        {chat.messages.map((m, i) => (
          <div key={m.id ?? i} className={`chat-message chat-message-${m.role}`}>
            <div className="chat-message-content">{m.content}</div>
            {m.comment && <div className="chat-message-comment">💬 {m.comment}</div>}
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
        {chat.isStreaming && <div className="chat-panel-progress">⏳ {chat.progress || '진행 중...'}</div>}
      </div>

      <form
        className="chat-panel-input"
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
    </aside>
  )
}
