import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listPapers, registerPaper } from '../api/papers'
import { PaperRow } from './PaperRow'
import './Papers.css'

// 08-04 라이브 테스트 피드백으로 재구성(RoadMap "라이브러리 — 논문 카탈로그 화면
// 재구성" 참고): recommended/owned를 섞어 보여주던 걸 걷어내고 여기는 owned만.
// recommended는 "결국 관심사를 거쳐야만 생기는 상태"라 관심사 화면 쪽에 둔다.
export function Papers() {
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [doi, setDoi] = useState('')
  const [arxivId, setArxivId] = useState('')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['papers', 'owned'],
    queryFn: () => listPapers('owned'),
  })

  const registerMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('PDF 파일을 선택해주세요.')
      return registerPaper(file, doi || undefined, arxivId || undefined)
    },
    onSuccess: () => {
      setFile(null)
      setDoi('')
      setArxivId('')
      queryClient.invalidateQueries({ queryKey: ['papers'] })
    },
  })

  const result = registerMutation.data
  const titleWarning = result?.title_check?.status === 'different_paper' ? result.title_check : null

  return (
    <div>
      <h1>📄 논문</h1>

      <form
        className="paper-register-form"
        onSubmit={(e) => {
          e.preventDefault()
          registerMutation.mutate()
        }}
      >
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <div className="paper-register-form-row">
          <input placeholder="DOI (선택)" value={doi} onChange={(e) => setDoi(e.target.value)} />
          <input placeholder="arXiv id (선택)" value={arxivId} onChange={(e) => setArxivId(e.target.value)} />
        </div>
        <button type="submit" disabled={registerMutation.isPending}>
          {registerMutation.isPending ? '등록 중... (PDF 파싱 + 임베딩이라 시간이 걸릴 수 있습니다)' : '등록'}
        </button>
      </form>

      {registerMutation.isError && (
        <p className="paper-message paper-message-error">등록 실패: {(registerMutation.error as Error).message}</p>
      )}
      {result && !result.text_extractable && (
        <p className="paper-message paper-message-warning">
          스캔본으로 판단되어 저장하지 않았습니다 (페이지 {result.page_count}쪽, 텍스트 레이어 없음).
        </p>
      )}
      {result && result.text_extractable && (
        <p className="paper-message paper-message-success">
          등록 완료 — paper_id=`{result.paper_id}`, 청크 {result.chunk_count}개, {result.page_count}쪽
        </p>
      )}
      {titleWarning && (
        <p className="paper-message paper-message-warning">
          제목이 크게 달라 다른 논문일 수 있습니다 — 입력한 제목 '{titleWarning.given_title}' vs PDF 제목 '
          {titleWarning.pdf_title}'
        </p>
      )}

      <h2>보유 논문</h2>
      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="paper-message paper-message-error">조회 실패: {(error as Error).message}</p>}
      {data && data.papers.length === 0 && <p>등록된 논문이 없습니다.</p>}
      {data && data.papers.map((p) => <PaperRow key={p.paper_id} paper={p} />)}
    </div>
  )
}
