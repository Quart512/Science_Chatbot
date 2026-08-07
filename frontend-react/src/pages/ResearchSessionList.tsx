import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  closeResearchSession,
  listResearchSessions,
  renameResearchSession,
  type ResearchSession,
} from '../api/research'
import { EditableSessionTitle } from '../components/EditableSessionTitle'
import { ResearchIcon } from '../components/NavIcons'
import './SessionList.css'

// 왼쪽 네비 "연구 워크플로우" 라벨을 눌렀을 때 뜨는 화면 — ChatSessionList.tsx와
// 같은 이유·같은 패턴(08-06, 사용자 요청). 라벨=이 목록, "+"(Layout.tsx)=/research/new
// (NewResearchForm, Research.tsx가 threadId 없을 때 이미 보여주던 것 그대로).
//
// 08-06 후속 — 제목 행을 EditableSessionTitle로. 연구는 챗봇과 달리
// last_message_role 개념이 의미 없어서(사용자 결정 — "어느 단계인지가 이미
// 상태 역할을 한다") 상태 점 대신 stage 배지를 그대로 아래 줄에 놓는다.
export function ResearchSessionList() {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useQuery({ queryKey: ['research-sessions'], queryFn: listResearchSessions })
  const sessions = data?.sessions ?? []

  return (
    <div>
      <div className="session-list-header">
        <h1><ResearchIcon size={22} /> 연구 워크플로우</h1>
        <button className="session-list-new" onClick={() => navigate('/research/new')}>
          + 새 연구
        </button>
      </div>

      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="session-list-error">세션 목록 조회 실패</p>}
      {!isLoading && !isError && sessions.length === 0 && (
        <p className="session-list-empty">아직 진행 중인 연구가 없습니다 — "+ 새 연구"로 시작하세요.</p>
      )}

      <div className="session-grid">
        {sessions.map((s) => (
          <ResearchSessionCard key={s.thread_id} session={s} onOpen={() => navigate(`/research/${s.thread_id}`)} />
        ))}
      </div>
    </div>
  )
}

function ResearchSessionCard({ session, onOpen }: { session: ResearchSession; onOpen: () => void }) {
  const queryClient = useQueryClient()

  const renameMutation = useMutation({
    mutationFn: (title: string) => renameResearchSession(session.thread_id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-sessions'] }),
  })
  const closeMutation = useMutation({
    mutationFn: () => closeResearchSession(session.thread_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-sessions'] }),
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
        <span className="session-card-stage">{session.stage}</span>
        <span className="session-status-time">{session.updated_at.slice(0, 10)}</span>
      </div>
    </div>
  )
}
