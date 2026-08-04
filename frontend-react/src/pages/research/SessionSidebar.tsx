import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  advanceResearch,
  closeResearchSession,
  listResearchSessions,
  renameResearchSession,
  type ResearchSession,
} from '../../api/research'

interface Props {
  selectedThreadId: string | null
  onSelect: (threadId: string | null) => void
}

export function SessionSidebar({ selectedThreadId, onSelect }: Props) {
  const queryClient = useQueryClient()
  const { data, isError, error } = useQuery({ queryKey: ['research-sessions'], queryFn: listResearchSessions })
  const [topic, setTopic] = useState('')

  const startMutation = useMutation({
    mutationFn: async () => {
      const newThreadId = crypto.randomUUID()
      await advanceResearch(newThreadId, { stage: 'hypothesis', topic })
      return newThreadId
    },
    onSuccess: (newThreadId) => {
      setTopic('')
      queryClient.invalidateQueries({ queryKey: ['research-sessions'] })
      onSelect(newThreadId)
    },
  })

  return (
    <aside className="research-sidebar">
      <h3>연구 세션</h3>
      {isError && <p className="research-warning">세션 목록 조회 실패: {(error as Error).message}</p>}
      {data?.sessions.map((s) => (
        <SessionCard
          key={s.thread_id}
          session={s}
          isSelected={s.thread_id === selectedThreadId}
          onSelect={() => onSelect(s.thread_id)}
          onClosed={() => {
            if (selectedThreadId === s.thread_id) onSelect(null)
          }}
        />
      ))}

      <hr />
      <h3>새 연구 시작</h3>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (!topic) return
          startMutation.mutate()
        }}
      >
        <textarea
          className="research-textarea"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="연구 주제·질문"
        />
        <button type="submit" disabled={startMutation.isPending}>
          {startMutation.isPending ? '시작 중...' : '시작'}
        </button>
      </form>
      {startMutation.isError && <p className="research-warning">시작 실패: {(startMutation.error as Error).message}</p>}
    </aside>
  )
}

function SessionCard({
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
            <button type="button" className="research-session-close" onClick={() => closeMutation.mutate()} disabled={closeMutation.isPending}>
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
        <button className="research-session-close" onClick={() => closeMutation.mutate()} disabled={closeMutation.isPending}>
          닫기
        </button>
      </div>
    </div>
  )
}
