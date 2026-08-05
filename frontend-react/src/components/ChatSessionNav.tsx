import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { closeChatSession, listChatSessions, renameChatSession, type ChatSession } from '../api/chat'
import '../pages/Research.css'

// 챗봇 네비 항목 아래 중첩되는 세션 목록 — ResearchSessionNav.tsx와 완전히 같은
// 패턴(선택 상태는 URL `/chat/:threadId` 기준). research-session-* 클래스를 그대로
// 재사용한다(둘 다 같은 "세션 카드" 시각 언어라 새 이름을 만들 이유가 없음).
export function ChatSessionNav() {
  const { threadId: selectedThreadId } = useParams<{ threadId?: string }>()
  const navigate = useNavigate()
  const { data, isError } = useQuery({ queryKey: ['chat-sessions'], queryFn: listChatSessions })

  if (isError) {
    return <p className="research-warning research-session-nav-error">세션 목록 조회 실패</p>
  }

  return (
    <div className="research-session-nav">
      {data?.sessions.map((s) => (
        <ChatSessionNavItem
          key={s.thread_id}
          session={s}
          isSelected={s.thread_id === selectedThreadId}
          onSelect={() => navigate(`/chat/${s.thread_id}`)}
          onClosed={() => {
            if (selectedThreadId === s.thread_id) navigate('/chat')
          }}
        />
      ))}
    </div>
  )
}

function ChatSessionNavItem({
  session,
  isSelected,
  onSelect,
  onClosed,
}: {
  session: ChatSession
  isSelected: boolean
  onSelect: () => void
  onClosed: () => void
}) {
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      onClosed()
    },
  })

  function startEditing() {
    setTitle(session.title)
    setEditing(true)
  }

  if (editing) {
    return (
      <div className={`research-session-card ${isSelected ? 'research-session-card-selected' : ''}`}>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            renameMutation.mutate()
          }}
        >
          <input className="research-input" value={title} onChange={(e) => setTitle(e.target.value)} />
          <div className="research-session-actions">
            <div className="research-session-actions-left">
              <button type="submit" disabled={renameMutation.isPending}>
                {renameMutation.isPending ? '저장 중...' : '저장'}
              </button>
              <button type="button" onClick={() => setEditing(false)}>
                취소
              </button>
            </div>
            <button
              type="button"
              className="research-session-close"
              onClick={() => closeMutation.mutate()}
              disabled={closeMutation.isPending}
            >
              닫기
            </button>
          </div>
        </form>
      </div>
    )
  }

  return (
    <div className={`research-session-card ${isSelected ? 'research-session-card-selected' : ''}`}>
      <button className="research-session-select" onClick={onSelect}>
        {session.title}
      </button>
      <div className="research-session-actions">
        <div className="research-session-actions-left">
          <button onClick={startEditing}>수정</button>
        </div>
        <button
          className="research-session-close"
          onClick={() => closeMutation.mutate()}
          disabled={closeMutation.isPending}
        >
          닫기
        </button>
      </div>
    </div>
  )
}
