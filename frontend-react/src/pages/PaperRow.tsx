import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ANALYSIS_IN_PROGRESS, getPaperFileUrl, getPaperSummary, type PaperCatalogRow } from '../api/papers'

const STATUS_LABEL: Record<string, string> = {
  pending: '대기 중',
  analyzing: '분석 중...',
  failed: '분석 실패',
}

// 요약은 lazy 생성이라(paper_ingest.get_paper_summary 참고) 펼칠 때만 조회한다
// (enabled: expanded) — 목록에 논문이 많아져도 안 펼친 것까지 미리 부르지 않음.
export function PaperRow({ paper }: { paper: PaperCatalogRow }) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  // ④(08-05) — pending/analyzing이면 아직 청크가 없어 요약 조회가 에러로 끝난다(파싱이
  // 안 끝났으므로). untracked(기존 업로드로 등록된, ① 마이그레이션 이후 아무도 이 컬럼을
  // 안 채운 논문 — 실제로는 이미 분석 끝난 상태)·done·failed는 기존과 동일하게 시도한다.
  const inProgress = ANALYSIS_IN_PROGRESS.includes(paper.analysis_status)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['paper-summary', paper.paper_id],
    queryFn: () => getPaperSummary(paper.paper_id),
    enabled: expanded && !inProgress,
  })

  return (
    <div className="paper-row">
      <button className="paper-row-header" onClick={() => setExpanded((v) => !v)}>
        {/* 우선순위: title > filename > paper_id(해시) — 08-04 사용자 요청("해쉬값은
            최후순위, 파일명이 그 앞"). arxiv/DOI로 등록된 논문은 title이 항상 있어
            filename까지 갈 일이 드물고, 서지정보를 못 찾은 업로드만 filename을 보여준다. */}
        <span>
          {paper.title || paper.filename || paper.paper_id}
          {STATUS_LABEL[paper.analysis_status] && (
            <span className={`paper-row-status paper-row-status-${paper.analysis_status}`}>
              {STATUS_LABEL[paper.analysis_status]}
            </span>
          )}
        </span>
        <span>{expanded ? '▲' : '▼'}</span>
      </button>
      {paper.authors && <p className="paper-row-meta">{paper.authors} {paper.year && `(${paper.year})`}</p>}
      <p className="paper-row-dates">
        등록 {paper.created_at.slice(0, 10)}
        {paper.updated_at !== paper.created_at && ` · 수정 ${paper.updated_at.slice(0, 10)}`}
      </p>

      {/* 원본 조회 ③(08-05) — file_path가 있는 논문만(②-B "트래킹에 추가"로 등록된
          것). 기존 업로드 다이얼로그로 등록된 논문은 원본을 애초에 안 남겨서 이
          섹션을 아예 안 보여준다. iframe은 <details> 안에 둬 실제로 열 때만
          PDF를 내려받게 함 — 요약(enabled: expanded)과 같은 lazy 원칙. */}
      {expanded && paper.file_path && (
        <div className="paper-row-file">
          <p className="paper-row-meta">
            <code>{paper.file_path}</code>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(paper.file_path!)
                setCopied(true)
                setTimeout(() => setCopied(false), 1500)
              }}
            >
              {copied ? '복사됨' : '경로 복사'}
            </button>
          </p>
          <details>
            <summary>원본 PDF 보기</summary>
            <iframe
              className="paper-row-pdf-frame"
              src={getPaperFileUrl(paper.paper_id)}
              title={`${paper.title || paper.filename || paper.paper_id} 원본`}
            />
          </details>
        </div>
      )}

      {expanded && (
        <div className="paper-row-summary">
          {inProgress && (
            <p>
              {paper.analysis_status === 'analyzing'
                ? '분석이 진행 중입니다 (PDF 파싱 + 임베딩) — 잠시 후 자동으로 갱신됩니다.'
                : '분석 대기 중입니다 — 곧 시작됩니다.'}
            </p>
          )}
          {!inProgress && isLoading && <p>요약 불러오는 중... (처음 조회면 LLM 호출이라 시간이 걸릴 수 있습니다)</p>}
          {!inProgress && isError && <p style={{ color: 'crimson' }}>요약 조회 실패: {(error as Error).message}</p>}
          {!inProgress && data && (
            <>
              <h4>핵심 주장</h4>
              <ul>
                {data.extraction.core_claims.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
              {data.extraction.evidence.length > 0 && (
                <>
                  <h4>근거</h4>
                  <ul>
                    {data.extraction.evidence.map((e, i) => (
                      <li key={i}>
                        [{e.kind}] {e.detail}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {data.extraction.author_stated_limitations.length > 0 && (
                <>
                  <h4>저자가 밝힌 한계</h4>
                  <ul>
                    {data.extraction.author_stated_limitations.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                </>
              )}
              {data.extraction.unresolved_questions.length > 0 && (
                <>
                  <h4>미해결 지점</h4>
                  <ul>
                    {data.extraction.unresolved_questions.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </>
              )}
              {data.extraction.code_data_availability && (
                <p>
                  <strong>코드/데이터 공개:</strong> {data.extraction.code_data_availability}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
