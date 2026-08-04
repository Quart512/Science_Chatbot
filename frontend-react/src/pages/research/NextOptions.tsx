import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { advanceResearch, type ResearchState } from '../../api/research'
import { hasStaleDownstream, nextOptions } from './constants'

interface Props {
  threadId: string
  values: ResearchState
  tipValues: ResearchState
  fromCheckpointId: string | null
  onAdvanced: () => void
}

// frontend/views/research.py의 _render_next_options()와 같은 계약.
export function NextOptions({ threadId, values, tipValues, fromCheckpointId, onAdvanced }: Props) {
  const options = nextOptions(values)

  let newRefs: ResearchState['references'] = []
  if (fromCheckpointId !== null) {
    const pastIds = new Set((values.references ?? []).map((r) => r.paper_id))
    newRefs = (tipValues.references ?? []).filter((r) => !pastIds.has(r.paper_id))
  }

  return (
    <>
      {options.map((opt) => (
        <OptionForm
          key={`${opt.target}_${opt.label}`}
          threadId={threadId}
          opt={opt}
          values={values}
          fromCheckpointId={fromCheckpointId}
          newRefs={newRefs}
          onAdvanced={onAdvanced}
        />
      ))}
    </>
  )
}

function OptionForm({
  threadId,
  opt,
  values,
  fromCheckpointId,
  newRefs,
  onAdvanced,
}: {
  threadId: string
  opt: ReturnType<typeof nextOptions>[number]
  values: ResearchState
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
  const showStaleWarning = fromCheckpointId === null && hasStaleDownstream(values, opt.target)

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
      {showStaleWarning && (
        <p className="research-warning">
          ⚠️ 재생성하면 이후 단계에 이미 만들어둔 값이 낡은 채로 남습니다(자동으로 지워지지 않음)
        </p>
      )}
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
