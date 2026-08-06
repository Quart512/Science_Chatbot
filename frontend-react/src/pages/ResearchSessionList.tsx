import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  closeResearchSession,
  listResearchSessions,
  renameResearchSession,
  type ResearchSession,
} from '../api/research'
import './SessionList.css'

// 왼쪽 네비 "연구 워크플로우" 라벨을 눌렀을 때 뜨는 화면 — ChatSessionList.tsx와
// 같은 이유·같은 패턴(08-06, 사용자 요청). 라벨=이 목록, "+"(Layout.tsx)=/research/new
// (NewResearchForm, Research.tsx가 threadId 없을 때 이미 보여주던 것 그대로).
export function ResearchSessionList() {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useQuery({ queryKey: ['research-sessions'], queryFn: listResearchSessions })
  const sessions = data?.sessions ?? []

  return (
    <div>
      <div className="session-list-header">
        <h1>🧬 연구 워크플로우</h1>
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
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(session.title)

  const renameMutation = useMutation({
    mutationFn: () => renameResearchSession(session.thread_id, title),
    onSuccess: () => {
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['research-sessions'] })
    },
  })
  const closeMutation = useMutation({
    mutationFn: () => closeResearchSession(session.thread_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['research-sessions'] }),
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
        <span className="session-card-stage">{session.stage}</span>
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
