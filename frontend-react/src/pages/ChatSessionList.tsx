import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { closeChatSession, listChatSessions, renameChatSession, type ChatSession } from '../api/chat'
import './SessionList.css'

// 왼쪽 네비 "챗봇" 라벨을 눌렀을 때 뜨는 화면(08-06, 사용자 요청) — 예전엔 라벨을
// 누르면 threadId 없는 /chat이 곧장 "새 대화" 폼을 보여줬는데, 그러면 "지금 열려있는
// 대화들을 훑어보고 싶다"는 요구를 채울 화면이 없었다(사이드바의 좁은 세션 목록뿐).
// 이제 라벨=이 목록 화면, "+"(Layout.tsx)=/chat/new(새 대화 폼)로 의미를 분리한다.
// 사이드바 ChatSessionNav.tsx와 같은 react-query 키('chat-sessions')를 써서 캐시를
// 공유 — 어느 쪽에서 이름을 바꾸거나 닫아도 서로 즉시 반영된다.
export function ChatSessionList() {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useQuery({ queryKey: ['chat-sessions'], queryFn: listChatSessions })
  const sessions = data?.sessions ?? []

  return (
    <div>
      <div className="session-list-header">
        <h1>💬 챗봇</h1>
        <button className="session-list-new" onClick={() => navigate('/chat/new')}>
          + 새 대화
        </button>
      </div>

      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="session-list-error">세션 목록 조회 실패</p>}
      {!isLoading && !isError && sessions.length === 0 && (
        <p className="session-list-empty">아직 대화가 없습니다 — "+ 새 대화"로 시작하세요.</p>
      )}

      <div className="session-grid">
        {sessions.map((s) => (
          <ChatSessionCard key={s.thread_id} session={s} onOpen={() => navigate(`/chat/${s.thread_id}`)} />
        ))}
      </div>
    </div>
  )
}

function ChatSessionCard({ session, onOpen }: { session: ChatSession; onOpen: () => void }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(session.title)

  const renameMutation = useMutation({
    mutationFn: () => renameChatSession(session.thread_id, title),
    onSuccess: () => {
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    },
  })
  const closeMutation = useMutation({
    mutationFn: () => closeChatSession(session.thread_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chat-sessions'] }),
  })

  function startEditing() {
    setTitle(session.title)
    setEditing(true)
  }

  if (editing) {
    return (
      <div className="session-card">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            renameMutation.mutate()
          }}
        >
          <input className="session-input" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
          <div className="session-card-actions">
            <button type="submit" disabled={renameMutation.isPending}>
              {renameMutation.isPending ? '저장 중...' : '저장'}
            </button>
            <button type="button" onClick={() => setEditing(false)}>
              취소
            </button>
          </div>
        </form>
      </div>
    )
  }

  return (
    <div className="session-card">
      <button className="session-card-open" onClick={onOpen}>
        <strong>{session.title}</strong>
        <span className="session-card-meta">{session.updated_at.slice(0, 10)}</span>
      </button>
      <div className="session-card-actions">
        <button onClick={startEditing}>수정</button>
        <button className="session-card-close" onClick={() => closeMutation.mutate()} disabled={closeMutation.isPending}>
          닫기
        </button>
      </div>
    </div>
  )
}
