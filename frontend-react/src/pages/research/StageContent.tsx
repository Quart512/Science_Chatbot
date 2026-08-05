import type { ResearchState } from '../../api/research'
import { formatNumberedList, resolveCitations } from './constants'

// frontend/views/research.py의 _render_stage_content()와 같은 계약.
export function StageContent({ values }: { values: ResearchState }) {
  const stage = values.stage
  const references = values.references ?? []

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
          <h3>{values.title || '(제목 없음)'}</h3>
          {(['abstract', 'introduction', 'methods', 'results', 'discussion'] as const).map((field) => (
            <div key={field}>
              <p>
                <strong>{{ abstract: '초록', introduction: '서론', methods: '방법', results: '결과', discussion: '고찰' }[field]}</strong>
              </p>
              <p>{resolveCitations(values[field], references)}</p>
            </div>
          ))}
          {values.citations?.length > 0 && (
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
