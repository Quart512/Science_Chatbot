import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getResearchHistory, type HistoryEntry } from '../api/research'
import { SessionSidebar } from './research/SessionSidebar'
import { StageContent } from './research/StageContent'
import { NextOptions } from './research/NextOptions'
import { DraftEditor } from './research/DraftEditor'
import { STAGES, STAGE_DONE_FIELD, STAGE_LABELS } from './research/constants'
import './Research.css'

// frontend/views/research.py 전체와 같은 계약 — 세션 사이드바 + 5단계 완료 체크
// 타임라인 + 체크포인트 탭("탭처럼 왔다갔다") + 현재 단계 내용 + 다음 단계 선택 패널.
export function Research() {
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [viewCheckpointId, setViewCheckpointId] = useState<string | null>(null)

  const historyQuery = useQuery({
    queryKey: ['research-history', selectedThreadId],
    queryFn: () => getResearchHistory(selectedThreadId!),
    enabled: selectedThreadId !== null,
  })

  return (
    <div className="research-layout">
      <SessionSidebar
        selectedThreadId={selectedThreadId}
        onSelect={(id) => {
          setSelectedThreadId(id)
          setViewCheckpointId(null)
        }}
      />

      <div className="research-main">
        {!selectedThreadId && <p>왼쪽에서 세션을 선택하거나 새 연구를 시작하세요.</p>}

        {selectedThreadId && historyQuery.isLoading && <p>불러오는 중...</p>}
        {selectedThreadId && historyQuery.isError && (
          <p className="research-warning">히스토리 조회 실패: {(historyQuery.error as Error).message}</p>
        )}

        {selectedThreadId && historyQuery.data && historyQuery.data.history.length > 0 && (
          <ResearchThreadView
            threadId={selectedThreadId}
            history={historyQuery.data.history}
            viewCheckpointId={viewCheckpointId}
            setViewCheckpointId={setViewCheckpointId}
          />
        )}
      </div>
    </div>
  )
}

function ResearchThreadView({
  threadId,
  history,
  viewCheckpointId,
  setViewCheckpointId,
}: {
  threadId: string
  history: HistoryEntry[]
  viewCheckpointId: string | null
  setViewCheckpointId: (id: string | null) => void
}) {
  const tip = history[history.length - 1]
  const validIds = new Set(history.map((e) => e.checkpoint_id))
  const effectiveViewId = viewCheckpointId && validIds.has(viewCheckpointId) ? viewCheckpointId : tip.checkpoint_id
  const selected = history.find((e) => e.checkpoint_id === effectiveViewId)!
  const isTip = selected.checkpoint_id === tip.checkpoint_id
  const values = selected.values

  return (
    <>
      <div className="research-timeline">
        {STAGES.map(([stageKey, label]) => {
          const done = Boolean(tip.values[STAGE_DONE_FIELD[stageKey]])
          const isCurrent = tip.values.stage === stageKey
          return (
            <span key={stageKey} className="research-timeline-item">
              {done ? '✅' : '⬜'} {label}
              {isCurrent && ' ← 현재'}
            </span>
          )
        })}
      </div>

      <div className="research-tabs">
        {history.map((entry) => {
          const ts = entry.created_at ? entry.created_at.slice(11, 16) : ''
          const isTipEntry = entry.checkpoint_id === tip.checkpoint_id
          return (
            <button
              key={entry.checkpoint_id}
              className={`research-tab ${entry.checkpoint_id === effectiveViewId ? 'research-tab-active' : ''}`}
              onClick={() => setViewCheckpointId(entry.checkpoint_id)}
            >
              {STAGE_LABELS[entry.stage] ?? entry.stage} {ts}
              {isTipEntry && ' (현재)'}
            </button>
          )
        })}
      </div>

      {!isTip && <p className="research-caption">과거 시점입니다 — 여기서 진행하면 이 시점을 기준으로 새로 이어집니다.</p>}
      {values.comment && <p className="research-comment">{values.comment}</p>}

      <StageContent values={values} />

      {values.stage === 'writing' && values.abstract && isTip && (
        <DraftEditor threadId={threadId} values={values} checkpointId={selected.checkpoint_id} />
      )}

      <hr />
      <h3>다음으로 갈 수 있는 곳</h3>
      <NextOptions
        threadId={threadId}
        values={values}
        tipValues={tip.values}
        fromCheckpointId={isTip ? null : selected.checkpoint_id}
        onAdvanced={() => setViewCheckpointId(null)}
      />
    </>
  )
}
