import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { advanceResearch, type ResearchState } from '../../api/research'
import { nextOptions, stageIndex } from './constants'

interface Props {
  threadId: string
  values: ResearchState
  tipValues: ResearchState
  fromCheckpointId: string | null
  onAdvanced: () => void
}

// frontend/views/research.py의 _render_next_options()에서 한 단계 더 나간 계약(08-04
// 사용자 지적) — 옵션마다 낡은-값 경고가 반복돼서 거슬렸던 걸, "진행"(정방향, 경고
// 없음)과 "재시도"(같은/이전 단계로, 경고는 그룹 전체에 한 번만)로 나눔. 목표 단계가
// 현재 단계보다 뒤면 진행, 아니면(같거나 앞) 재시도 — 이 인덱스 비교가 예전의
// hasStaleDownstream 판정과 동치다(각 단계 진입 노드가 자기보다 뒤 단계 필드를 항상
// 리셋하므로, "재시도" 대상은 반드시 지금 값이 이미 채워져 있어 경고가 항상 뜬다).
export function NextOptions({ threadId, values, tipValues, fromCheckpointId, onAdvanced }: Props) {
  const options = nextOptions(values)
  const currentIndex = stageIndex(values.stage)
  const forwardOptions = options.filter((o) => stageIndex(o.target) > currentIndex)
  const retryOptions = options.filter((o) => stageIndex(o.target) <= currentIndex)

  let newRefs: ResearchState['references'] = []
  if (fromCheckpointId !== null) {
    const pastIds = new Set((values.references ?? []).map((r) => r.paper_id))
    newRefs = (tipValues.references ?? []).filter((r) => !pastIds.has(r.paper_id))
  }

  return (
    <>
      {forwardOptions.length > 0 && (
        <div className="research-option-group">
          <h4>진행</h4>
          {forwardOptions.map((opt) => (
            <OptionForm
              key={`${opt.target}_${opt.label}`}
              threadId={threadId}
              opt={opt}
              fromCheckpointId={fromCheckpointId}
              newRefs={newRefs}
              onAdvanced={onAdvanced}
            />
          ))}
        </div>
      )}

      {retryOptions.length > 0 && (
        <div className="research-option-group">
          <h4>재시도</h4>
          {fromCheckpointId === null && (
            <p className="research-warning">
              ⚠️ 재생성하면 이후 단계에 이미 만들어둔 값이 낡은 채로 남습니다(자동으로 지워지지 않음)
            </p>
          )}
          {retryOptions.map((opt) => (
            <OptionForm
              key={`${opt.target}_${opt.label}`}
              threadId={threadId}
              opt={opt}
              fromCheckpointId={fromCheckpointId}
              newRefs={newRefs}
              onAdvanced={onAdvanced}
            />
          ))}
        </div>
      )}
    </>
  )
}

function OptionForm({
  threadId,
  opt,
  fromCheckpointId,
  newRefs,
  onAdvanced,
}: {
  threadId: string
  opt: ReturnType<typeof nextOptions>[number]
  fromCheckpointId: string | null
  newRefs: ResearchState['references']
  onAdvanced: () => void
}) {
  const queryClient = useQueryClient()
  const [resultsText, setResultsText] = useState('')
  const [keepIds, setKeepIds] = useState<Set<string>>(new Set())

  const mutation = useMutation({
    mutationFn: () =>
      advanceResearch(threadId, {
        stage: opt.target,
        experiment_results: opt.needsResults ? resultsText : undefined,
        from_checkpoint_id: fromCheckpointId ?? undefined,
        keep_reference_paper_ids: fromCheckpointId ? Array.from(keepIds) : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-history', threadId] })
      queryClient.invalidateQueries({ queryKey: ['research-sessions'] })
      onAdvanced()
    },
  })

  const label = opt.label + (opt.recommended ? ' [추천]' : '')

  function toggleKeep(paperId: string) {
    setKeepIds((prev) => {
      const next = new Set(prev)
      if (next.has(paperId)) next.delete(paperId)
      else next.add(paperId)
      return next
    })
  }

  return (
    <div className="research-option">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (opt.needsResults && !resultsText) return
          mutation.mutate()
        }}
      >
        {opt.needsResults && (
          <textarea
            className="research-textarea"
            value={resultsText}
            onChange={(e) => setResultsText(e.target.value)}
            placeholder="실험 결과"
          />
        )}

        {newRefs.length > 0 && (
          <div className="research-ref-diff">
            <p className="research-warning">
              ⚠️ 이 시점 이후 새로 찾은 참고문헌 {newRefs.length}편이 있습니다 — 이 갈래에 남길 것만 선택하세요(기본은 버림).
            </p>
            {newRefs.map((r) => (
              <label key={r.paper_id} className="research-ref-checkbox">
                <input type="checkbox" checked={keepIds.has(r.paper_id)} onChange={() => toggleKeep(r.paper_id)} />
                {r.title}
                {r.reasoning && ` — ${r.reasoning}`}
              </label>
            ))}
          </div>
        )}

        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? '진행 중...' : label}
        </button>
      </form>
      {mutation.isError && <p className="research-warning">요청 실패: {(mutation.error as Error).message}</p>}
    </div>
  )
}
