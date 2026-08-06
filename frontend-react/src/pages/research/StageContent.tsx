import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateResearchDraft, type ResearchState } from '../../api/research'
import { formatNumberedList, resolveCitations } from './constants'

const DRAFT_FIELDS = [
  ['title', '제목'],
  ['abstract', '초록'],
  ['introduction', '서론'],
  ['methods', '방법'],
  ['results', '결과'],
  ['discussion', '고찰'],
] as const

const DRAFT_BODY_LABELS: Record<string, string> = {
  abstract: '초록',
  introduction: '서론',
  methods: '방법',
  results: '결과',
  discussion: '고찰',
}

interface Props {
  values: ResearchState
  threadId: string
  // tip을 보고 있을 때만 수정 가능(과거 시점은 읽기 전용) — DraftEditor.tsx가 원래
  // isTip 조건으로 렌더 자체를 안 하던 것과 같은 제약, 호출부(Research.tsx)가 판단해 넘긴다.
  canEdit: boolean
}

// frontend/views/research.py의 _render_stage_content()에서 출발한 계약.
//
// 08-06 화면 개선 ⑪(RoadMap "프론트 개선 백로그" 참고) — 예전엔 이 컴포넌트가 읽기
// 전용 표시만 하고, 별도 DraftEditor.tsx가 그 아래 접힌 "초안 수정"에서 같은 내용을
// 원문 그대로(마커 안 바뀜) 편집 가능한 textarea로 다시 보여줬다(같은 걸 두 번). 이제
// "수정" 버튼 하나로 같은 자리에서 표시 모드 ↔ 편집 모드를 전환한다 — 표시 모드는
// resolveCitations()로 [CITE:id] 마커를 서지 형식으로 바꿔 보여주고, 편집 모드는
// 저장 시 마커가 안 깨지도록 원문 그대로 보여준다(DraftEditor.tsx가 원래 남겼던 이유
// 그대로 유지, 두 모드가 같은 자리에서 전환되는 것만 바뀜).
export function StageContent({ values, threadId, canEdit }: Props) {
  const stage = values.stage
  const references = values.references ?? []
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [fields, setFields] = useState<Record<string, string>>(() =>
    Object.fromEntries(DRAFT_FIELDS.map(([key]) => [key, (values[key] as string) ?? ''])),
  )

  const mutation = useMutation({
    mutationFn: () => updateResearchDraft(threadId, fields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-history', threadId] })
      setEditing(false)
    },
  })

  function startEditing() {
    // "수정"을 누르는 시점의 최신 값으로 다시 채운다(EquipmentRow 등 기존 인라인
    // 편집 패턴과 같은 이유 — RoadMap "'수정' UX 통일" 설계 노트 참고).
    setFields(Object.fromEntries(DRAFT_FIELDS.map(([key]) => [key, (values[key] as string) ?? ''])))
    setEditing(true)
  }

  return (
    <>
      {stage === 'hypothesis' && values.hypothesis && (
        <section>
          <h3>가설</h3>
          <p>{values.hypothesis}</p>
          <p className="research-caption">근거: {values.rationale}</p>
          <p className="research-caption">검증 가능한 예측: {values.testable_prediction}</p>
        </section>
      )}

      {stage === 'design' && values.procedure && (
        <section>
          <h3>실험 설계</h3>
          <p>
            <strong>독립변수</strong>: {values.independent_variable}
          </p>
          <p>
            <strong>종속변수</strong>: {values.dependent_variable}
          </p>
          <p>
            <strong>통제변수</strong>: {values.controlled_variables}
          </p>
          <p>
            <strong>필요 장비</strong>: {values.equipment_needed}
          </p>
          <p>
            <strong>절차</strong>
          </p>
          <p className="research-pre">{formatNumberedList(values.procedure)}</p>
        </section>
      )}

      {stage === 'operation' && values.outcome && (
        <section>
          <h3>실험 결과 분석</h3>
          <p>
            <strong>입력한 결과</strong>: {values.experiment_results}
          </p>
          <p>
            <strong>분석</strong>: {values.analysis}
          </p>
          <p>
            <strong>판정</strong>: <code>{values.outcome}</code>
          </p>
        </section>
      )}

      {stage === 'report' && values.experiment_report && (
        <section>
          <h3>실험 보고서</h3>
          <p className="research-pre">{values.experiment_report}</p>
        </section>
      )}

      {stage === 'writing' && values.abstract && (
        <section>
          <div className="research-draft-topbar">
            {editing ? (
              <input
                className="research-input research-draft-title-input"
                value={fields.title}
                onChange={(e) => setFields((f) => ({ ...f, title: e.target.value }))}
              />
            ) : (
              <h3>{values.title || '(제목 없음)'}</h3>
            )}
            {canEdit &&
              (editing ? (
                <div className="research-draft-actions">
                  <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
                    {mutation.isPending ? '저장 중...' : '저장'}
                  </button>
                  <button type="button" onClick={() => setEditing(false)}>
                    취소
                  </button>
                </div>
              ) : (
                <button type="button" className="research-draft-edit-toggle" onClick={startEditing}>
                  ✎ 수정
                </button>
              ))}
          </div>

          {editing && (
            <p className="research-caption research-draft-marker-hint">
              [CITE:논문id] 는 인용 마커입니다 — 표시 모드에선 서지 형식으로 바뀌어 보이지만 편집 중엔 원문 그대로입니다. 지우지 마세요.
            </p>
          )}

          {(['abstract', 'introduction', 'methods', 'results', 'discussion'] as const).map((field) => (
            <div key={field}>
              <p>
                <strong>{DRAFT_BODY_LABELS[field]}</strong>
              </p>
              {editing ? (
                <textarea
                  className="research-textarea"
                  value={fields[field]}
                  onChange={(e) => setFields((f) => ({ ...f, [field]: e.target.value }))}
                />
              ) : (
                <p>{resolveCitations(values[field], references)}</p>
              )}
            </div>
          ))}

          {mutation.isError && <p className="research-warning">저장 실패: {(mutation.error as Error).message}</p>}

          {!editing && values.citations?.length > 0 && (
            <details>
              <summary>인용 근거</summary>
              {values.citations.map((c, i) => {
                const title = references.find((r) => r.paper_id === c.paper_id)?.title ?? c.paper_id
                return (
                  <p key={i} className="research-caption">
                    - {title}: {c.reasoning}
                  </p>
                )
              })}
            </details>
          )}
        </section>
      )}

      {references.length > 0 && (
        <details>
          <summary>참고문헌 ({references.length}편)</summary>
          {references.map((r) => (
            <p key={r.paper_id} className="research-caption">
              - [{r.source}] {r.title || r.paper_id}
              {r.reasoning && ` — ${r.reasoning}`}
            </p>
          ))}
        </details>
      )}
    </>
  )
}
