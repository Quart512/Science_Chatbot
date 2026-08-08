import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ANALYSIS_IN_PROGRESS,
  deletePaper,
  getPaperFileUrl,
  getPaperSummary,
  movePaper,
  type Evidence,
  type PaperCatalogRow,
} from '../api/papers'
import { trackLibraryFile } from '../api/library'
import { FullscreenModal } from '../components/FullscreenModal'
import { ReorderButtons } from '../components/ReorderButtons'

const STATUS_LABEL: Record<string, string> = {
  pending: '대기 중',
  analyzing: '분석 중...',
  failed: '분석 실패',
}

const EVIDENCE_KIND_LABEL: Record<Evidence['kind'], string> = {
  experimental: '실험적',
  theoretical: '이론적',
  simulation: '시뮬레이션 기반',
}

// 요약 표시 형식 — 산문 렌더링(08-05, RoadMap 예정 표 참고). 저장(extraction_json)은
// 구조화된 그대로 두고, 화면 표시만 <ul> 목록 대신 문단으로 바꾼 파생 뷰 — LLM 재호출
// 없이 순수 템플릿이라 실패해도 원본 구조가 안 깨진다. LLM이 추출한 문장(core_claims
// 등)은 내용을 예측할 수 없어 그 뒤에 조사(을/를 등)를 직접 붙이지 않는다 — 대신
// 항상 마침표로 문장을 맺고, 조사가 필요한 자리는 내가 직접 쓴 고정 문구에만 쓴다.
function ensureSentence(text: string): string {
  const trimmed = text.trim()
  if (trimmed === '') return trimmed
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`
}

function renderClaimsProse(claims: string[]): string {
  return claims.map((c, i) => (i === 0 ? ensureSentence(c) : `또한 ${ensureSentence(c)}`)).join(' ')
}

function renderEvidenceProse(evidence: Evidence[]): string {
  return evidence
    .map((e) => `${EVIDENCE_KIND_LABEL[e.kind]} 근거: ${ensureSentence(e.detail || '세부사항 언급 없음')}`)
    .join(' ')
}

function renderListProse(items: string[]): string {
  return items.map(ensureSentence).join(' ')
}

// 요약은 lazy 생성이라(paper_ingest.get_paper_summary 참고) 펼칠 때만 조회한다
// (enabled: expanded) — 목록에 논문이 많아져도 안 펼친 것까지 미리 부르지 않음.
//
// fileMissing(08-05, 화면 개선 ⑩ 설계 노트) — 추적은 됐지만(paper.file_path가 있음)
// library/ 스캔에서 그 경로가 더는 안 보이는 경우(사용자가 파일을 지우거나 옮김).
// Papers.tsx가 papers·library/files 두 쿼리를 대조해 계산해서 넘긴다.
// 확대(전체화면) 버튼 아이콘 — 코드베이스에 아이콘 라이브러리가 없어(▾/▸/✎/✕처럼
// 전부 순수 글리프) 새 의존성 없이 SVG를 직접 인라인. 대각선 화살표 2개로 "넓히기"를
// 표현하는 통상적인 fullscreen/expand 아이콘 모양(stroke만 있어 currentColor로 테마 대응).
function ExpandIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="15 3 21 3 21 9" />
      <polyline points="9 21 3 21 3 15" />
      <line x1="21" y1="3" x2="14" y2="10" />
      <line x1="3" y1="21" x2="10" y2="14" />
    </svg>
  )
}

export function PaperRow({
  paper, fileMissing = false, isFirst, isLast,
}: { paper: PaperCatalogRow; fileMissing?: boolean; isFirst: boolean; isLast: boolean }) {
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const [pdfFullscreen, setPdfFullscreen] = useState(false)
  const [pdfOpen, setPdfOpen] = useState(false)
  const moveMutation = useMutation({
    mutationFn: (direction: 'up' | 'down') => movePaper(paper.paper_id, direction),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers'] }),
  })
  // 08-08 — 사용자 요청. "library/에서 지워도 다시 스캔이 미추적 파일로 인식 못 한다"는
  // 별도 지적에는 감지 기능을 새로 안 만들기로 했다(요약 등 추출 결과는 원본이 없어도
  // 남아 그 나름대로 값어치가 있다는 사용자 판단) — 대신 원치 않는 카탈로그 항목을
  // 직접 지우는 이 버튼만 추가한다. 확인 대화상자는 이 코드베이스 다른 삭제(실험도구·
  // 지식노트)도 안 쓰는 관례라 그대로 따른다.
  const deleteMutation = useMutation({
    mutationFn: () => deletePaper(paper.paper_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers'] }),
  })
  // 논문 분석 멈춤 버그 대응(08-06, RoadMap 참고) — failed는 청크가 아예 없어 요약을
  // 조회해봤자 항상 에러라 시도 자체를 건너뛴다(untracked/done만 기존처럼 시도).
  // 재시도는 register_paper()를 다시 태우는 기존 트래킹 엔드포인트 재사용. doi/arxiv_id를
  // 반드시 같이 넘겨야 한다 — 안 그러면 원래 arxiv/doi로 등록됐던 논문이 해시 기반의
  // 다른 paper_id로 재계산돼 원본과 분리된 고아 중복이 생긴다(실제로 겪은 버그).
  const retryMutation = useMutation({
    mutationFn: () =>
      trackLibraryFile(paper.file_path!, {
        doi: paper.doi ?? undefined,
        arxiv_id: paper.arxiv_id ?? undefined,
        title: paper.title || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['papers'] })
      queryClient.invalidateQueries({ queryKey: ['paper-summary', paper.paper_id] })
    },
  })
  const inProgress = ANALYSIS_IN_PROGRESS.includes(paper.analysis_status)
  const failed = paper.analysis_status === 'failed'
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['paper-summary', paper.paper_id],
    queryFn: () => getPaperSummary(paper.paper_id),
    enabled: expanded && !inProgress && !failed,
  })

  return (
    <div className="library-reorder-row">
      <ReorderButtons
        isFirst={isFirst}
        isLast={isLast}
        pending={moveMutation.isPending}
        onMoveUp={() => moveMutation.mutate('up')}
        onMoveDown={() => moveMutation.mutate('down')}
      />
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
      <div className="paper-row-dates-and-actions">
        <p className="paper-row-dates">
          등록 {paper.created_at.slice(0, 10)}
          {paper.updated_at !== paper.created_at && ` · 수정 ${paper.updated_at.slice(0, 10)}`}
        </p>
        <button
          type="button"
          className="paper-row-delete"
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
        >
          {deleteMutation.isPending ? '삭제 중...' : '삭제'}
        </button>
      </div>
      {deleteMutation.isError && (
        <p className="paper-message paper-message-error">삭제 실패: {(deleteMutation.error as Error).message}</p>
      )}

      {/* 원본 조회 ③(08-05) — file_path가 있는 논문만. ⑤ 이전(tempfile만 쓰고
          버리던 시절)에 등록된 옛 논문만 원본이 없어 이 섹션을 안 보여준다.
          iframe은 <details> 안에 둬 실제로 열 때만 PDF를 내려받게 함 —
          요약(enabled: expanded)과 같은 lazy 원칙. */}
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
          {fileMissing ? (
            <p className="paper-message paper-message-warning">
              ⚠️ library/에서 이 파일을 찾을 수 없습니다 — 옮겨졌거나 삭제된 것 같습니다. 원래 위치로 되돌리거나 "다시
              스캔" 후 재등록하세요.
            </p>
          ) : (
            <>
              {/* 08-08 — 사용자 지적: "토글로 뷰어 열기"(원래 <summary> 텍스트 링크)가
                  잘 안 보이고, 작은 아이콘 버튼(전체화면)이 오히려 눈에 띄어 둘의 역할이
                  헷갈렸다. <details>를 걷어내고 버튼 두 개를 나란히 둔다 — 예전에
                  전체화면 버튼이 갖고 있던 테두리 있는 "버튼처럼 보이는" 스타일을 토글
                  쪽으로 옮기고, 전체화면은 별도 라벨이 있는 버튼으로 새로 만든다. */}
              <div className="paper-row-pdf-controls">
                <button
                  type="button"
                  className="paper-row-pdf-toggle"
                  aria-expanded={pdfOpen}
                  onClick={() => setPdfOpen((v) => !v)}
                >
                  {pdfOpen ? '원본 PDF 접기' : '원본 PDF 보기'}
                </button>
                <button
                  type="button"
                  className="paper-row-pdf-fullscreen-btn"
                  onClick={() => setPdfFullscreen(true)}
                >
                  <ExpandIcon />
                  전체화면으로 보기
                </button>
              </div>
              {/* iframe은 pdfOpen일 때만 렌더 — 실제로 열 때만 PDF를 내려받는 lazy
                  원칙은 그대로 유지(요약의 enabled: expanded와 같은 이유). */}
              {pdfOpen && (
                <iframe
                  className="paper-row-pdf-frame"
                  src={getPaperFileUrl(paper.paper_id)}
                  title={`${paper.title || paper.filename || paper.paper_id} 원본`}
                />
              )}
            </>
          )}
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
          {failed && (
            <div className="paper-message paper-message-error">
              <p>
                분석에 실패했습니다{fileMissing ? ' — 원본 파일도 찾을 수 없습니다.' : '.'}
                {retryMutation.data && ' 다시 시도를 시작했습니다 — 잠시 후 상태가 갱신됩니다.'}
              </p>
              {!fileMissing && paper.file_path && (
                <button type="button" onClick={() => retryMutation.mutate()} disabled={retryMutation.isPending}>
                  {retryMutation.isPending ? '다시 시도 중...' : '다시 시도'}
                </button>
              )}
              {retryMutation.isError && <p>재시도 요청 실패: {(retryMutation.error as Error).message}</p>}
            </div>
          )}
          {/* 08-08 — "요약"에서 "추출 결과"로. "요약"은 압축(모으는 방향)을 뜻하는데
              `PaperExtraction`이 실제로 하는 건 필드 다섯 개로 가르는 분리다
              (RoadMap "08-08 결론" 참고). 함수·엔드포인트 이름(`get_paper_summary`,
              `/summary`)은 그대로 둔다 — 한국어 명칭만 바꾸는 개명이다. */}
          {!inProgress && !failed && isLoading && <p>추출 결과 불러오는 중... (처음 조회면 LLM 호출이라 시간이 걸릴 수 있습니다)</p>}
          {!inProgress && !failed && isError && <p style={{ color: 'crimson' }}>추출 결과 조회 실패: {(error as Error).message}</p>}
          {!inProgress && data && (
            <>
              <h4>핵심 주장</h4>
              <p className="paper-row-prose">{renderClaimsProse(data.extraction.core_claims)}</p>
              {data.extraction.evidence.length > 0 && (
                <>
                  <h4>근거</h4>
                  <p className="paper-row-prose">{renderEvidenceProse(data.extraction.evidence)}</p>
                </>
              )}
              {data.extraction.author_stated_limitations.length > 0 && (
                <>
                  <h4>저자가 밝힌 한계</h4>
                  <p className="paper-row-prose">{renderListProse(data.extraction.author_stated_limitations)}</p>
                </>
              )}
              {data.extraction.unresolved_questions.length > 0 && (
                <>
                  <h4>미해결 지점</h4>
                  <p className="paper-row-prose">{renderListProse(data.extraction.unresolved_questions)}</p>
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

      {/* expanded 상태와 별개로 둔다 — 전체화면을 연 채로 행이 접혀도(드문 경우) 뷰어가
          갑자기 사라지지 않게. */}
      {pdfFullscreen && paper.file_path && (
        <FullscreenModal title={paper.title || paper.filename || paper.paper_id} onClose={() => setPdfFullscreen(false)}>
          <iframe
            className="pdf-fullscreen-frame"
            src={getPaperFileUrl(paper.paper_id)}
            title={`${paper.title || paper.filename || paper.paper_id} 원본 (전체화면)`}
          />
        </FullscreenModal>
      )}
      </div>
    </div>
  )
}
