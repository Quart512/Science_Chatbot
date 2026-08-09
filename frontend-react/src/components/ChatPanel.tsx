import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listChatSessions } from '../api/chat'
import { CHAT_EFFORTS, groupMessagesIntoTurns, useChatThread } from '../hooks/useChatThread'
import { useAvailableChatModels } from '../hooks/useLocalModel'
import { useChatPanelAutoShow } from '../hooks/useChatPanelAutoShow'
import { getLastViewedChatThreadId } from '../lib/lastViewedChat'
import { ChatIcon } from './NavIcons'
import { Markdown } from './Markdown'
import { StreamProgress } from './StreamProgress'
import './ChatPanel.css'

// 셸에 항상 떠 있는 챗 패널(08-04 설계 노트 "React 전환" 참고) — 연구 워크플로우 등
// 다른 화면을 보면서 동시에 쓸 수 있게 하는 게 이 컴포넌트의 존재 이유.
//
// 화면 개선 ⑤(08-06) 갱신 — 예전엔 마운트마다 crypto.randomUUID()로 새 thread_id를
// 발급해서 새로고침하면 대화가 사라졌다. 이제 방금 쓰던 세션을 이어서 연다 — 왼쪽 독립
// 챗 화면(Chat.tsx)이 세션 여러 개를 관리하는 "허브"고, 여긴 그중 하나만 항상 보여주는
// "바로가기"라는 역할 분담. 세션이 하나도 없을 때만(첫 사용) 새 uuid로 새 대화를 시작한다.
// 두 화면이 같은 react-query 키('chat-sessions')를 보므로, 왼쪽에서 다른 세션에 메시지를
// 보내 그게 최신이 되면 이 패널도 자동으로 그 세션을 따라간다(전송 후 invalidateQueries는
// useChatThread 안에서 처리).
//
// 08-07 정정 — "방금 쓰던"을 처음엔 sessions[0](updated_at DESC, 즉 "마지막으로 답변을
// 요청한" 세션)으로 구현했는데, 사용자 재현으로 "마지막으로 본" 세션이어야 한다는 게
// 드러났다(챗 a에 질문 → 챗 b를 읽기만 함 → 다른 화면으로 이동 → 패널에 a가 뜨는 버그).
// `updated_at`은 `touch_session()`이 `/query`(답변 요청) 때만 갱신해 "열람 시각"을 표현할
// 수 없어서다. localStorage(`lib/lastViewedChat.ts`)에 왼쪽 챗 화면이 기록해둔 thread_id를
// 우선 쓰고, 그 세션이 삭제됐으면 sessions[0]로 폴백한다.
//
// 08-06 후속 — 챗봇 화면(왼쪽)에 이미 같은 세션이 떠 있으니 이 패널은 거기선
// 중복이다. ① 챗봇 화면(/chat, /chat/new, /chat/:id)에서는 무조건 닫는다.
// ② 챗봇을 벗어날 때 다시 열지는 설정(useChatPanelAutoShow, Settings.tsx)에
// 따른다 — 껐다/켰다는 여전히 오른쪽 버튼으로 항상 가능, 이 설정은 "챗봇에서 나갈
// 때"에만 적용된다(다른 화면끼리 이동할 땐 사용자가 마지막으로 골라둔 열림/닫힘을
// 그대로 유지, 아래 effect가 "방금 챗봇을 나왔을 때"만 판단하는 이유).
function isChatRoute(pathname: string): boolean {
  return pathname === '/chat' || pathname.startsWith('/chat/')
}

export function ChatPanel() {
  const { pathname } = useLocation()
  const { autoShow } = useChatPanelAutoShow()
  const [open, setOpen] = useState(!isChatRoute(pathname))
  const wasOnChatRoute = useRef(isChatRoute(pathname))

  useEffect(() => {
    const isChat = isChatRoute(pathname)
    if (isChat) {
      setOpen(false)
    } else if (wasOnChatRoute.current && autoShow) {
      setOpen(true)
    }
    wasOnChatRoute.current = isChat
  }, [pathname, autoShow])

  const [freshThreadId] = useState(() => crypto.randomUUID())
  const sessionsQuery = useQuery({ queryKey: ['chat-sessions'], queryFn: listChatSessions })
  const sessions = sessionsQuery.data?.sessions
  // "마지막으로 답변을 요청한" 챗(sessions[0], updated_at 기준) 대신 "마지막으로 본" 챗을
  // 연다(RoadMap 항목) — 왼쪽 챗 화면이 기록해둔 thread_id를 우선 찾고, 그 세션이 그 사이
  // 삭제됐으면(목록에 없으면) sessions[0]로 폴백한다.
  const lastViewedId = getLastViewedChatThreadId()
  const lastViewedSession = sessions?.find((s) => s.thread_id === lastViewedId)
  const mostRecent = lastViewedSession ?? sessions?.[0]
  const threadId = mostRecent?.thread_id ?? freshThreadId

  const chat = useChatThread(threadId, { hydrateOnMount: mostRecent !== undefined })

  // 설치 안 한 로컬 모델은 드롭다운에 안 띄운다(08-09) — 고르면 100% 접속 실패였다.
  const availableModels = useAvailableChatModels()

  if (isChatRoute(pathname)) {
    return null
  }

  if (!open) {
    return (
      <button className="chat-panel-toggle" onClick={() => setOpen(true)}>
        <ChatIcon size={16} /> 챗 열기
      </button>
    )
  }

  return (
    <aside className="chat-panel">
      <div className="chat-panel-header">
        <span><ChatIcon size={16} /> 챗</span>
        <button onClick={() => setOpen(false)} aria-label="챗 닫기">
          ✕
        </button>
      </div>

      <div className="chat-panel-controls">
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
      <p className="chat-panel-thread-id">thread_id: {threadId}</p>
      <button className="chat-panel-register-interest" onClick={chat.registerAsInterest}>
        💡 이 대화를 관심사로 등록
      </button>
      {chat.draftError && <p className="chat-panel-error">{chat.draftError}</p>}
      {chat.deleteError && <p className="chat-panel-error">{chat.deleteError}</p>}

      <div className="chat-panel-messages">
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
        className="chat-panel-input"
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
    </aside>
  )
}
