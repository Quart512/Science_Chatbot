import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { closeChatSession, listChatSessions, renameChatSession, type ChatSession } from '../api/chat'
import { EditableSessionTitle } from './EditableSessionTitle'
import '../pages/Research.css'
import '../pages/SessionList.css'

// 챗봇 네비 항목 아래 중첩되는 세션 목록 — ResearchSessionNav.tsx와 완전히 같은
// 패턴(선택 상태는 URL `/chat/:threadId` 기준). research-session-* 클래스를 그대로
// 재사용한다(둘 다 같은 "세션 카드" 시각 언어라 새 이름을 만들 이유가 없음).
//
// 08-06 화면 개선 — 제목 행이 EditableSessionTitle(수정/닫기를 제목과 같은 줄의
// 호버 아이콘으로)로 바뀌고, 그 아래 상태 줄(대기중/응답됨 + 최근 대화 미리보기)이
// 새로 생겼다.
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

  const renameMutation = useMutation({
    mutationFn: (title: string) => renameChatSession(session.thread_id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chat-sessions'] }),
  })
  const closeMutation = useMutation({
    mutationFn: () => closeChatSession(session.thread_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      onClosed()
    },
  })

  return (
    <div className={`research-session-card ${isSelected ? 'research-session-card-selected' : ''}`}>
      <EditableSessionTitle
        title={session.title}
        onOpen={onSelect}
        onRename={(title) => renameMutation.mutate(title)}
        onClose={() => closeMutation.mutate()}
        renamePending={renameMutation.isPending}
        closePending={closeMutation.isPending}
      />
      <div className="session-status-row">
        <span
          className={`session-status-dot session-status-dot-${session.last_message_role === 'user' ? 'waiting' : 'answered'}`}
          title={session.last_message_role === 'user' ? '대기중 — 아직 답이 없습니다' : '응답됨'}
        />
        {session.last_message_preview && <span className="session-status-preview">{session.last_message_preview}</span>}
      </div>
    </div>
  )
}
