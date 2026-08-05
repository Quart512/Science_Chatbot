import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listPapers, registerPaper } from '../api/papers'
import { listLibraryFiles, trackLibraryFile } from '../api/library'
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

  // 서버측 파일 브라우저 ②-C(08-05) — 업로드 다이얼로그가 아니라 서버가 library/를
  // 스캔한 목록에서 고르는 경로. 브라우저는 고른 파일의 전체 경로를 안 주고 다이얼로그
  // 시작 위치도 못 정해서, "library/를 띄우는 업로드 UI"가 원리적으로 불가능하다
  // (RoadMap 설계 노트 "논문·노트 저장 방식 재설계" 항목 A).
  const {
    data: library,
    isLoading: libraryLoading,
    isError: libraryIsError,
    error: libraryError,
    isFetching: libraryFetching,
    refetch: refetchLibrary,
  } = useQuery({
    queryKey: ['library', 'files'],
    queryFn: listLibraryFiles,
  })

  const trackMutation = useMutation({
    mutationFn: (path: string) => trackLibraryFile(path),
    onSuccess: (data) => {
      // 두 목록 다 무효화한다 — 트래킹은 papers 테이블에 owned 행을 만들므로("보유 논문"이
      // 늘어남) 동시에 이 파일의 tracked 플래그도 true로 바뀐다(library/files 재스캔).
      queryClient.invalidateQueries({ queryKey: ['library', 'files'] })
      queryClient.invalidateQueries({ queryKey: ['papers'] })
      // 요약 캐시도 반드시 같이 버린다 — register_paper()는 재등록 시 그 paper_id의 문서를
      // doc_type 구분 없이 전부 지우는데(재등록 = 요약 캐시 무효화, 의도된 설계) 요약은
      // lazy라 그 자리에서 다시 안 만들어진다. PaperRow의 쿼리 키가 ['paper-summary', id]로
      // 위 ['papers'] 접두사 밖에 있어서, 안 지우면 **이미 삭제된 요약을 화면이 계속
      // 보여준다** — 08-05 ②-C 라이브 확인에서 실제로 재현했다(저장소엔 fulltext_chunk
      // 122개만 남았는데 화면엔 옛 요약이 그대로 떠 있었음).
      queryClient.invalidateQueries({ queryKey: ['paper-summary', data.paper_id] })
    },
  })

  const result = registerMutation.data
  const titleWarning = result?.title_check?.status === 'different_paper' ? result.title_check : null
  const trackResult = trackMutation.data

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

      <div className="library-section-header">
        <h2>library/ 폴더</h2>
        {/* 파일시스템 워처를 안 만들기로 한 결정(RoadMap 설계 노트 항목 F — Docker
            Desktop 바인드 마운트에서 inotify가 컨테이너로 잘 안 온다)의 대체 수단.
            화면 진입 시 스캔(useQuery 마운트) + 이 버튼으로 수동 재스캔이 전부다. */}
        <button type="button" onClick={() => refetchLibrary()} disabled={libraryFetching}>
          {libraryFetching ? '스캔 중...' : '다시 스캔'}
        </button>
      </div>
      <p className="library-hint">
        이 폴더에 PDF를 직접 넣어두면 여기 목록에 나타납니다. 파일을 옮기거나 이름을 바꿨다면 "다시 스캔"을 눌러주세요.
      </p>

      {libraryLoading && <p>스캔 중...</p>}
      {libraryIsError && (
        <p className="paper-message paper-message-error">스캔 실패: {(libraryError as Error).message}</p>
      )}
      {library && library.files.length === 0 && <p>library/ 폴더에 PDF가 없습니다.</p>}
      {library &&
        library.files.map((f) => (
          <div className="library-file" key={f.path}>
            <span className="library-file-path" title={f.path}>
              {f.path}
            </span>
            {f.tracked ? (
              <span className="library-file-tracked">추적 중</span>
            ) : (
              // isPending이면 다른 행의 버튼까지 전부 잠근다 — track은 파싱·청킹·임베딩을
              // 동기로 다 돌리는 무거운 호출이라(④ 파싱 분리 전까지는 그렇다) 동시에
              // 여러 개를 걸 이유가 없다.
              <button
                type="button"
                onClick={() => trackMutation.mutate(f.path)}
                disabled={trackMutation.isPending}
              >
                {trackMutation.isPending && trackMutation.variables === f.path
                  ? '분석 중... (PDF 파싱 + 임베딩)'
                  : '트래킹에 추가'}
              </button>
            )}
          </div>
        ))}

      {trackMutation.isError && (
        <p className="paper-message paper-message-error">트래킹 실패: {(trackMutation.error as Error).message}</p>
      )}
      {/* 스캔본은 register_paper()가 청크를 하나도 안 만들고 mark_owned()도 안 타므로
          목록에서 계속 "미추적"으로 남는다(②-B에서 그대로 두기로 한 기존 간극). 성공
          응답인데 목록이 안 바뀌는 셈이라, 왜 그런지를 여기서 반드시 말해줘야 한다. */}
      {trackResult && !trackResult.text_extractable && (
        <p className="paper-message paper-message-warning">
          스캔본으로 판단되어 저장하지 않았습니다 (페이지 {trackResult.page_count}쪽, 텍스트 레이어 없음) — 목록에는
          계속 미추적으로 남습니다.
        </p>
      )}
      {trackResult && trackResult.text_extractable && (
        <p className="paper-message paper-message-success">
          트래킹 완료 — paper_id=`{trackResult.paper_id}`, 청크 {trackResult.chunk_count}개, {trackResult.page_count}쪽
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
