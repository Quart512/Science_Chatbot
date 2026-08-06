import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  closeResearchSession,
  listResearchSessions,
  renameResearchSession,
  type ResearchSession,
} from '../api/research'
import { EditableSessionTitle } from './EditableSessionTitle'
import '../pages/Research.css'
import '../pages/SessionList.css'

// 연구 워크플로우 네비 항목 아래 중첩되는 세션 목록(08-04 사용자 지적 — "세션이
// 왼쪽에 있는 게 낫다"는 게 전역 좌측 네비 컬럼 자체를 말한 것이었다. 예전엔
// Research.tsx 안에 별도 사이드바 컬럼으로 분리해뒀는데, 셸이 이미 왼쪽 네비를
// 갖고 있다는 걸 다시 고려 안 하고 Streamlit research.py의 st.sidebar 구조를
// 그대로 포팅한 결과였다). 선택 상태는 URL(`/research/:threadId`)이 기준이라
// 새로고침해도 안 날아간다.
//
// 08-06 화면 개선 — 제목 행이 EditableSessionTitle로 바뀌고, 예전엔 제목 옆
// "(stage)"로만 붙던 단계 표시가 아래 배지 줄로 옮겨졌다(챗봇 쪽 상태 줄과 같은
// 자리, 시각 언어 통일 — 연구는 last_message_role 개념이 의미 없어서
// (사용자 결정) 대신 stage 배지를 놓는다).
export function ResearchSessionNav() {
  const { threadId: selectedThreadId } = useParams<{ threadId?: string }>()
  const navigate = useNavigate()
  const { data, isError } = useQuery({ queryKey: ['research-sessions'], queryFn: listResearchSessions })

  if (isError) {
    return <p className="research-warning research-session-nav-error">세션 목록 조회 실패</p>
  }

  return (
    <div className="research-session-nav">
      {data?.sessions.map((s) => (
        <SessionNavItem
          key={s.thread_id}
          session={s}
          isSelected={s.thread_id === selectedThreadId}
          onSelect={() => navigate(`/research/${s.thread_id}`)}
          onClosed={() => {
            if (selectedThreadId === s.thread_id) navigate('/research')
          }}
        />
      ))}
    </div>
  )
}

function SessionNavItem({
  session,
  isSelected,
  onSelect,
  onClosed,
}: {
  session: ResearchSession
  isSelected: boolean
  onSelect: () => void
  onClosed: () => void
}) {
  const queryClient = useQueryClient()

  const renameMutation = useMutation({
    mutationFn: (title: string) => renameResearchSession(session.thread_id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-sessions'] }),
  })
  const closeMutation = useMutation({
    mutationFn: () => closeResearchSession(session.thread_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-sessions'] })
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
        <span className="session-card-stage">{session.stage}</span>
        <span className="session-status-time">{session.updated_at.slice(0, 10)}</span>
      </div>
    </div>
  )
}
