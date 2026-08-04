import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { advanceResearch, getResearchHistory, type HistoryEntry } from '../api/research'
import { StageContent } from './research/StageContent'
import { NextOptions } from './research/NextOptions'
import { DraftEditor } from './research/DraftEditor'
import { BranchTimeline } from './research/BranchTimeline'
import { RetryReferencesButton } from './research/RetryReferencesButton'
import { nextOptions, STAGES_WITH_REFERENCES } from './research/constants'
import './Research.css'

// frontend/views/research.py 전체와 같은 계약이었던 데서 출발 — 브랜치형 타임라인
// (BranchTimeline, RoadMap "타임라인·체크 결합(브랜치형)" 설계 노트) + 현재 단계
// 내용 + 다음 단계 선택 패널. 예전엔 완료체크 타임라인과 체크포인트 탭이 따로였는데
// 이제 BranchTimeline 하나가 "지나온/현재/갈 수 있는 곳"을 전부 보여준다. 세션 목록은
// 08-04 사용자 지적으로 셸의 왼쪽 네비(`ResearchSessionNav`, 연구 워크플로우 항목
// 아래 중첩)로 옮겼고, 선택 상태는 `/research/:threadId` URL로 옮겨서 새로고침해도
// 안 날아간다(이전엔 컴포넌트 로컬 state였음).
export function Research() {
  const { threadId } = useParams<{ threadId?: string }>()
  const [viewCheckpointId, setViewCheckpointId] = useState<string | null>(null)

  const historyQuery = useQuery({
    queryKey: ['research-history', threadId],
    queryFn: () => getResearchHistory(threadId!),
    enabled: threadId !== undefined,
  })

  if (!threadId) {
    return <NewResearchForm />
  }

  return (
    <div>
      {historyQuery.isLoading && <p>불러오는 중...</p>}
      {historyQuery.isError && (
        <p className="research-warning">히스토리 조회 실패: {(historyQuery.error as Error).message}</p>
      )}

      {historyQuery.data && historyQuery.data.history.length > 0 && (
        <ResearchThreadView
          threadId={threadId}
          history={historyQuery.data.history}
          viewCheckpointId={viewCheckpointId}
          setViewCheckpointId={setViewCheckpointId}
        />
      )}
    </div>
  )
}

function NewResearchForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [topic, setTopic] = useState('')

  const startMutation = useMutation({
    mutationFn: async () => {
      const newThreadId = crypto.randomUUID()
      await advanceResearch(newThreadId, { stage: 'hypothesis', topic })
      return newThreadId
    },
    onSuccess: (newThreadId) => {
      queryClient.invalidateQueries({ queryKey: ['research-sessions'] })
      navigate(`/research/${newThreadId}`)
    },
  })

  return (
    <div>
      <h1>🧬 연구 워크플로우</h1>
      <p className="research-caption">왼쪽에서 세션을 선택하거나 새 연구를 시작하세요.</p>

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
      <BranchTimeline
        history={history}
        selectedCheckpointId={effectiveViewId}
        onSelect={setViewCheckpointId}
        nextOpts={nextOptions(tip.values)}
      />

      {!isTip && <p className="research-caption">과거 시점입니다 — 여기서 진행하면 이 시점을 기준으로 새로 이어집니다.</p>}
      {values.comment && <p className="research-comment">{values.comment}</p>}

      <StageContent values={values} />

      {isTip && STAGES_WITH_REFERENCES.has(values.stage) && (
        <RetryReferencesButton threadId={threadId} onRetried={() => setViewCheckpointId(null)} />
      )}

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
