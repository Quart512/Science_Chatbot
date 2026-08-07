import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { advanceResearch, type ResearchState } from '../../api/research'
import { STAGES, cellStatus, nextOptions, stageIndex, STAGE_FIELD_LABELS, buildRetryGuidance, type NextOption } from './constants'

interface Props {
  threadId: string
  values: ResearchState
  tipValues: ResearchState
  fromCheckpointId: string | null
  viewedCheckpointId: string
  onAdvanced: () => void
}

// 라벨이 옵션 안에서 유일하다는 게 nextOptions()의 실제 계약(같은 target을 공유하는
// 옵션끼리도 문구는 항상 다르다 — 예: "같은 설계로 재실험" vs "결과 다시 입력해 재분석")
// 이라 target+label 조합이면 이 화면 안에서 충분히 유일한 key가 된다.
function optionKey(opt: NextOption): string {
  return `${opt.target}_${opt.label}`
}

// 화면 개선 ③④(08-06, RoadMap "프론트 개선 백로그" 참고) — 예전엔 모든 방향의
// 입력창을 한꺼번에 펼쳐놓고 그중 하나를 버튼으로 고르게 했다. 이제는 각 옵션을
// BranchTimeline과 같은 5칸 다이어그램으로 미리 보여주고("이걸 고르면 이렇게 된다"),
// 고른 것 하나만 아래에 입력창이 뜬다 — 목업(사용자와 함께 설계)에서 검증한 그대로.
// 대상 목업 문서 참고: 03-05 다이어그램 미리보기 + 04-08 열린 질문 논의.
export function NextOptions({ threadId, values, tipValues, fromCheckpointId, viewedCheckpointId, onAdvanced }: Props) {
  const options = nextOptions(values)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)

  let newRefs: ResearchState['references'] = []
  if (fromCheckpointId !== null) {
    const pastIds = new Set((values.references ?? []).map((r) => r.paper_id))
    newRefs = (tipValues.references ?? []).filter((r) => !pastIds.has(r.paper_id))
  }

  if (options.length === 0) return null

  const selected = options.find((opt) => optionKey(opt) === selectedKey) ?? null

  return (
    <div className="research-next-options">
      <div className="research-candidate-list">
        {options.map((opt) => {
          const key = optionKey(opt)
          return (
            <button
              type="button"
              key={key}
              className={[
                'research-candidate-row',
                opt.recommended && 'research-candidate-row-recommended',
                selectedKey === key && 'research-candidate-row-selected',
              ].filter(Boolean).join(' ')}
              onClick={() => setSelectedKey((k) => (k === key ? null : key))}
            >
              <span className="research-candidate-cells">
                {STAGES.map(([stageKey, label]) => (
                  <span key={stageKey} className={`research-branch-cell research-branch-cell-${cellStatus(opt.target, stageKey)}`}>
                    {label}
                  </span>
                ))}
              </span>
              <span className="research-candidate-label">{opt.label}</span>
              {opt.recommended && <span className="research-candidate-badge">추천</span>}
            </button>
          )
        })}
      </div>

      {selected ? (
        <OptionForm
          key={`${viewedCheckpointId}_${selectedKey}`}
          threadId={threadId}
          opt={selected}
          values={values}
          isRetry={stageIndex(selected.target) <= stageIndex(values.stage)}
          fromCheckpointId={fromCheckpointId}
          newRefs={newRefs}
          onAdvanced={onAdvanced}
          onDeselect={() => setSelectedKey(null)}
        />
      ) : (
        <p className="research-candidate-empty">위에서 다이어그램을 하나 고르면 여기에 그 단계에 맞는 입력창이 뜹니다.</p>
      )}
    </div>
  )
}

function OptionForm({
  threadId,
  opt,
  values,
  isRetry,
  fromCheckpointId,
  newRefs,
  onAdvanced,
  onDeselect,
}: {
  threadId: string
  opt: NextOption
  values: ResearchState
  isRetry: boolean
  fromCheckpointId: string | null
  newRefs: ResearchState['references']
  onAdvanced: () => void
  onDeselect: () => void
}) {
  const queryClient = useQueryClient()
  const [resultsText, setResultsText] = useState('')
  const [keepIds, setKeepIds] = useState<Set<string>>(new Set())
  const [guidanceText, setGuidanceText] = useState('')
  // 재시도 대상 단계의 필드를 직접 고칠 수 있는 입력창(08-04 후속 — RoadMap "재생성
  // 시 사용자 피드백/지시 반영") — hypothesis/design만 대상(STAGE_FIELD_LABELS 참고).
  const editableFields = isRetry ? STAGE_FIELD_LABELS[opt.target] : undefined
  const [draftFields, setDraftFields] = useState<Record<string, string>>(
    () => Object.fromEntries((editableFields ?? []).map(([field]) => [field, (values[field] as string) ?? ''])),
  )

  const mutation = useMutation({
    mutationFn: () =>
      advanceResearch(threadId, {
        stage: opt.target,
        experiment_results: opt.needsResults ? resultsText : undefined,
        user_guidance: isRetry ? buildRetryGuidance(opt.target, draftFields, values, guidanceText) : undefined,
        from_checkpoint_id: fromCheckpointId ?? undefined,
        keep_reference_paper_ids: fromCheckpointId ? Array.from(keepIds) : undefined,
        action_label: opt.label,
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
      <div className="research-option-header">
        <strong>{label}</strong>
        <button type="button" className="research-option-deselect" onClick={onDeselect}>
          ✕ 선택 해제
        </button>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (opt.needsResults && !resultsText) return
          mutation.mutate()
        }}
      >
        {isRetry && (
          <p className="research-warning">
            ⚠️ 재생성하면 이후 단계에 이미 만들어둔 값이 낡은 채로 남습니다(자동으로 지워지지 않음)
          </p>
        )}

        {opt.needsResults && (
          <textarea
            className="research-textarea"
            value={resultsText}
            onChange={(e) => setResultsText(e.target.value)}
            placeholder="실험 결과"
          />
        )}

        {isRetry && (
          <div className="research-retry-guidance">
            <textarea
              className="research-textarea"
              value={guidanceText}
              onChange={(e) => setGuidanceText(e.target.value)}
              placeholder="AI에게 방향을 지시하세요(선택) — 예: 더 초보적인 단계로, 더 간단한 장비로"
            />
            {editableFields && (
              <details>
                <summary>직접 수정</summary>
                {editableFields.map(([field, fieldLabel]) => (
                  <div key={field}>
                    <label className="research-caption">{fieldLabel}</label>
                    <textarea
                      className="research-textarea"
                      value={draftFields[field]}
                      onChange={(e) => setDraftFields((f) => ({ ...f, [field]: e.target.value }))}
                    />
                  </div>
                ))}
              </details>
            )}
          </div>
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
