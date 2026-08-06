import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { closeChatSession, listChatSessions, renameChatSession, type ChatSession } from '../api/chat'
import { EditableSessionTitle } from '../components/EditableSessionTitle'
import './SessionList.css'

// 왼쪽 네비 "챗봇" 라벨을 눌렀을 때 뜨는 화면(08-06, 사용자 요청) — 예전엔 라벨을
// 누르면 threadId 없는 /chat이 곧장 "새 대화" 폼을 보여줬는데, 그러면 "지금 열려있는
// 대화들을 훑어보고 싶다"는 요구를 채울 화면이 없었다(사이드바의 좁은 세션 목록뿐).
// 이제 라벨=이 목록 화면, "+"(Layout.tsx)=/chat/new(새 대화 폼)로 의미를 분리한다.
// 사이드바 ChatSessionNav.tsx와 같은 react-query 키('chat-sessions')를 써서 캐시를
// 공유 — 어느 쪽에서 이름을 바꾸거나 닫아도 서로 즉시 반영된다.
//
// 08-06 후속 — 제목 행을 EditableSessionTitle로, 카드 아래 줄에 대기중/응답됨
// 상태 점 + 최근 대화 미리보기(둘 다 /api/chat/sessions가 체크포인트에서 직접
// 계산해 줌, main.py 참고)를 추가.
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

  const renameMutation = useMutation({
    mutationFn: (title: string) => renameChatSession(session.thread_id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chat-sessions'] }),
  })
  const closeMutation = useMutation({
    mutationFn: () => closeChatSession(session.thread_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chat-sessions'] }),
  })

  return (
    <div className="session-card">
      <EditableSessionTitle
        title={session.title}
        onOpen={onOpen}
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
        <span className="session-status-time">{session.updated_at.slice(0, 10)}</span>
      </div>
    </div>
  )
}
