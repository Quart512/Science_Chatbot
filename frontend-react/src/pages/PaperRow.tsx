import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getPaperSummary, type PaperCatalogRow } from '../api/papers'

// 요약은 lazy 생성이라(paper_ingest.get_paper_summary 참고) 펼칠 때만 조회한다
// (enabled: expanded) — 목록에 논문이 많아져도 안 펼친 것까지 미리 부르지 않음.
export function PaperRow({ paper }: { paper: PaperCatalogRow }) {
  const [expanded, setExpanded] = useState(false)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['paper-summary', paper.paper_id],
    queryFn: () => getPaperSummary(paper.paper_id),
    enabled: expanded,
  })

  return (
    <div className="paper-row">
      <button className="paper-row-header" onClick={() => setExpanded((v) => !v)}>
        {/* 우선순위: title > filename > paper_id(해시) — 08-04 사용자 요청("해쉬값은
            최후순위, 파일명이 그 앞"). arxiv/DOI로 등록된 논문은 title이 항상 있어
            filename까지 갈 일이 드물고, 서지정보를 못 찾은 업로드만 filename을 보여준다. */}
        <span>{paper.title || paper.filename || paper.paper_id}</span>
        <span>{expanded ? '▲' : '▼'}</span>
      </button>
      {paper.authors && <p className="paper-row-meta">{paper.authors} {paper.year && `(${paper.year})`}</p>}
      <p className="paper-row-dates">
        등록 {paper.created_at.slice(0, 10)}
        {paper.updated_at !== paper.created_at && ` · 수정 ${paper.updated_at.slice(0, 10)}`}
      </p>

      {expanded && (
        <div className="paper-row-summary">
          {isLoading && <p>요약 불러오는 중... (처음 조회면 LLM 호출이라 시간이 걸릴 수 있습니다)</p>}
          {isError && <p style={{ color: 'crimson' }}>요약 조회 실패: {(error as Error).message}</p>}
          {data && (
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
