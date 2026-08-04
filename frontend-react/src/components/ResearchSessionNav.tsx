import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  closeResearchSession,
  listResearchSessions,
  renameResearchSession,
  type ResearchSession,
} from '../api/research'
import '../pages/Research.css'

// 연구 워크플로우 네비 항목 아래 중첩되는 세션 목록(08-04 사용자 지적 — "세션이
// 왼쪽에 있는 게 낫다"는 게 전역 좌측 네비 컬럼 자체를 말한 것이었다. 예전엔
// Research.tsx 안에 별도 사이드바 컬럼으로 분리해뒀는데, 셸이 이미 왼쪽 네비를
// 갖고 있다는 걸 다시 고려 안 하고 Streamlit research.py의 st.sidebar 구조를
// 그대로 포팅한 결과였다). 선택 상태는 URL(`/research/:threadId`)이 기준이라
// 새로고침해도 안 날아간다.
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-sessions'] })
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
        {session.title} ({session.stage})
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
