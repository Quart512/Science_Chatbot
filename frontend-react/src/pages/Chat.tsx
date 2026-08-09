import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CHAT_EFFORTS, groupMessagesIntoTurns, useChatThread } from '../hooks/useChatThread'
import { useAvailableChatModels } from '../hooks/useLocalModel'
import { ChatIcon } from '../components/NavIcons'
import { Markdown } from '../components/Markdown'
import { StreamProgress } from '../components/StreamProgress'
import { setLastViewedChatThreadId } from '../lib/lastViewedChat'
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

  // 설치 안 한 로컬 모델은 드롭다운에 안 띄운다(08-09) — 고르면 100% 접속 실패였다.
  const availableModels = useAvailableChatModels()

  // 오른쪽 패널(ChatPanel.tsx)이 "마지막으로 답변을 요청한" 챗 대신 "마지막으로 본" 챗을
  // 열 수 있게, 실제로 URL을 가진 스레드를 열람할 때만 기록한다(RoadMap 항목 참고 — 여기
  // 조건이 urlThreadId인 이유: 이 화면이 새 대화 초안 단계(`/chat/new`, 아직 아무 응답도
  // 없는 상태)일 땐 "본 챗"이라 부를 실체가 아직 없고, 첫 메시지 전송 후 위 onFirstMessageSent가
  // URL을 바꾸면 이 effect가 그 시점에 자연히 한 번 더 돈다).
  useEffect(() => {
    if (urlThreadId) setLastViewedChatThreadId(urlThreadId)
  }, [urlThreadId])

  return (
    <div className="chat-page">
      <div className="chat-page-header">
        <h1><ChatIcon size={22} /> 챗</h1>
        <div className="chat-page-controls">
          <select value={chat.model} onChange={(e) => chat.setModel(e.target.value)}>
            {availableModels.map((m) => (
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
          <p className="chat-page-empty">과학에 대해 궁금한 걸 물어보세요.</p>
        )}
        {groupMessagesIntoTurns(chat.messages).map((turn, ti) => (
          <div className="chat-turn" key={turn[0].id ?? `turn-${ti}`}>
            {turn.map((m, i) => (
              <div key={m.id ?? i} className={`chat-message chat-message-${m.role}`}>
                <div className="chat-message-content"><Markdown text={m.content} /></div>
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
          placeholder="과학에 대해 궁금한 걸 물어보세요"
          disabled={chat.isStreaming}
        />
        <button type="submit" disabled={chat.isStreaming || !chat.input.trim()}>
          전송
        </button>
      </form>
    </div>
  )
}
