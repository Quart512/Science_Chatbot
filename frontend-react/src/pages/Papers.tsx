import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ANALYSIS_IN_PROGRESS, listPapers, registerPaper, type PaperSort } from '../api/papers'
import { listLibraryFiles, trackLibraryFile } from '../api/library'
import { PaperRow } from './PaperRow'
import { PaperIcon } from '../components/NavIcons'
import './Papers.css'

const SORT_LABELS: Record<PaperSort, string> = {
  created_desc: '등록 최신순',
  created_asc: '등록 오래된순',
  updated_desc: '수정 최신순',
  updated_asc: '수정 오래된순',
}

// 08-04 라이브 테스트 피드백으로 재구성(RoadMap "라이브러리 — 논문 카탈로그 화면
// 재구성" 참고): recommended/owned를 섞어 보여주던 걸 걷어내고 여기는 owned만.
// recommended는 "결국 관심사를 거쳐야만 생기는 상태"라 관심사 화면 쪽에 둔다.
export function Papers() {
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [doi, setDoi] = useState('')
  const [arxivId, setArxivId] = useState('')
  const [title, setTitle] = useState('')
  // sort는 빈 값(undefined)이 "사용자 지정 순서"(수동 정렬, sort_order) — 08-06.
  // 정렬이나 검색어가 켜지면 위/아래 순서 버튼을 끈다(아래 manualOrder) — sort_order
  // 기준이 아닌 화면에서 버튼을 눌러도 눈에 보이는 변화가 없는 혼란을 막기 위해서다.
  const [sort, setSort] = useState<PaperSort | ''>('')
  const [search, setSearch] = useState('')
  const manualOrder = sort === '' && search === ''

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['papers', 'owned', sort, search],
    queryFn: () => listPapers('owned', sort || undefined, search || undefined),
    // ④(08-05) — 트래킹은 이제 즉시 반환되고 분석(파싱·청킹·임베딩)은 서버 백그라운드에서
    // 돈다. pending/analyzing인 논문이 하나라도 있으면 2초마다 다시 불러 done/failed
    // 전환을 잡아낸다 — 없으면 폴링을 끈다(항상 켜두면 아무 일도 없을 때도 계속 조회하게 됨).
    refetchInterval: (query) => {
      const papers = query.state.data?.papers ?? []
      const inProgress = papers.some((p) => ANALYSIS_IN_PROGRESS.includes(p.analysis_status))
      return inProgress ? 2000 : false
    },
  })

  const registerMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('PDF 파일을 선택해주세요.')
      return registerPaper(file, doi || undefined, arxivId || undefined, title || undefined)
    },
    onSuccess: () => {
      setFile(null)
      setDoi('')
      setArxivId('')
      setTitle('')
      queryClient.invalidateQueries({ queryKey: ['papers'] })
      // ⑤(08-05)부터 업로드도 library/에 파일을 남기므로, trackMutation과 같은 이유로
      // library/files도 같이 무효화해야 "library/ 폴더" 섹션이 방금 올린 파일을
      // 곧바로 "추적 중"으로 보여준다(안 그러면 "다시 스캔"을 눌러야만 반영됨).
      queryClient.invalidateQueries({ queryKey: ['library', 'files'] })
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
  const trackResult = trackMutation.data

  return (
    <div>
      <h1><PaperIcon size={22} /> 논문</h1>

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
        {/* 08-05 — arxiv_id 없이는 자동 조회가 안 걸려 제목 넣을 방법이 없던 문제
            (RoadMap 예정 표 "비-arXiv 논문 제목 입력" 항목). DOI/arXiv id를 같이 적어도
            이 값이 우선한다(백엔드 "명시값 우선" 규칙). */}
        <input
          placeholder="제목 (선택 — DOI/arXiv로 자동으로 안 채워질 때 직접 입력)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <button type="submit" disabled={registerMutation.isPending}>
          {registerMutation.isPending ? '등록 중...' : '등록'}
        </button>
      </form>

      {registerMutation.isError && (
        <p className="paper-message paper-message-error">등록 실패: {(registerMutation.error as Error).message}</p>
      )}
      {/* ⑤(08-05)부터 업로드도 library/에 파일을 남기고 트래킹과 같은 경로(비동기)를
          탄다 — "시작됐다"만 알리고 진행 상태는 아래 "보유 논문" 목록의 PaperRow
          배지가 보여준다(trackResult 메시지와 같은 패턴). */}
      {result && (
        <p className="paper-message paper-message-success">
          등록됨 — paper_id=`{result.paper_id}`, 분석이 백그라운드에서 진행됩니다. 아래 "보유 논문" 목록에서 진행
          상태를 확인하세요.
        </p>
      )}

      <hr />

      {/* 화면 개선 ⑩(08-05, RoadMap "프론트 개선 백로그" 참고) — 예전엔 이 목록에
          추적된 파일까지 다 보여줘서 아래 "보유 논문"과 같은 논문이 두 번 나왔다.
          제3안(의미로 분리) 채택: 여기는 "아직 라이브러리에 안 넣은 파일"만 — 추적된
          파일은 보유 논문 목록에만 나온다. 두 목록의 의미가 갈리면서 중복이 원인부터
          사라진다(감추기가 아니라). */}
      <div className="library-section-header">
        <h2>library/ 폴더 — 미추적 파일</h2>
        {/* 파일시스템 워처를 안 만들기로 한 결정(RoadMap 설계 노트 항목 F — Docker
            Desktop 바인드 마운트에서 inotify가 컨테이너로 잘 안 온다)의 대체 수단.
            화면 진입 시 스캔(useQuery 마운트) + 이 버튼으로 수동 재스캔이 전부다. */}
        <button type="button" onClick={() => refetchLibrary()} disabled={libraryFetching}>
          {libraryFetching ? '스캔 중...' : '다시 스캔'}
        </button>
      </div>
      <p className="library-hint">
        이 폴더에 PDF를 직접 넣어두면 여기 목록에 나타납니다. 파일을 옮기거나 이름을 바꿨다면 "다시 스캔"을 눌러주세요.
        추적에 추가하면 아래 "보유 논문" 목록으로 옮겨갑니다.
      </p>

      {libraryLoading && <p>스캔 중...</p>}
      {libraryIsError && (
        <p className="paper-message paper-message-error">스캔 실패: {(libraryError as Error).message}</p>
      )}
      {library && library.files.every((f) => f.tracked) && <p>추적되지 않은 파일이 없습니다.</p>}
      {library &&
        library.files
          .filter((f) => !f.tracked)
          .map((f) => (
            <div className="library-file" key={f.path}>
              <span className="library-file-path" title={f.path}>
                {f.path}
              </span>
              {/* ④(08-05)부터 track 요청 자체는 등록(해시 계산 + pending 행 생성)만 동기로
                  하고 바로 반환된다 — isPending 구간이 짧아져 다른 행까지 잠글 이유가
                  약해졌지만, 같은 파일 중복 클릭 방지 목적으로 계속 남겨둔다. */}
              <button
                type="button"
                onClick={() => trackMutation.mutate(f.path)}
                disabled={trackMutation.isPending}
              >
                {trackMutation.isPending && trackMutation.variables === f.path ? '등록 중...' : '트래킹에 추가'}
              </button>
            </div>
          ))}

      {trackMutation.isError && (
        <p className="paper-message paper-message-error">트래킹 실패: {(trackMutation.error as Error).message}</p>
      )}
      {/* ④부터 파싱·청킹·임베딩은 백그라운드에서 돈다 — 여기선 "시작됐다"만 알리고,
          진행 상태(분석 중/완료/실패)는 아래 "보유 논문" 목록의 PaperRow 배지가 보여준다
          (papers 쿼리가 진행 중인 논문이 있는 동안 자동으로 폴링됨). */}
      {trackResult && (
        <p className="paper-message paper-message-success">
          등록됨 — paper_id=`{trackResult.paper_id}`, 분석이 백그라운드에서 진행됩니다. 아래 "보유 논문" 목록에서 진행
          상태를 확인하세요.
        </p>
      )}

      <hr />

      <h2>보유 논문</h2>
      <div className="paper-list-controls">
        <input
          type="search"
          placeholder="제목으로 검색"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={sort} onChange={(e) => setSort(e.target.value as PaperSort | '')}>
          <option value="">사용자 지정 순서</option>
          {(Object.keys(SORT_LABELS) as PaperSort[]).map((s) => (
            <option key={s} value={s}>
              {SORT_LABELS[s]}
            </option>
          ))}
        </select>
      </div>
      {!manualOrder && (
        <p className="library-hint">정렬·검색 중에는 순서 버튼이 꺼집니다 — "사용자 지정 순서"로 돌아가면 다시 켜집니다.</p>
      )}
      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="paper-message paper-message-error">조회 실패: {(error as Error).message}</p>}
      {data && data.papers.length === 0 && <p>등록된 논문이 없습니다.</p>}
      {data &&
        data.papers.map((p, i) => (
          // fileMissing — ⑩ 설계 노트가 같이 정하라고 남겨둔 "추적됐지만 파일이 사라진"
          // 경우. library/files 스캔 결과에 이 경로가 없으면 사용자가 파일을 지웠거나
          // 옮긴 것 — 새 백엔드 필드 없이 이미 불러온 두 쿼리(papers·library/files)를
          // 대조하는 것만으로 계산된다. library가 아직 안 불려왔으면(로딩 중) 성급하게
          // "없음"으로 단정하지 않음(false 기본값).
          <PaperRow
            key={p.paper_id}
            paper={p}
            fileMissing={!!p.file_path && !!library && !library.files.some((f) => f.path === p.file_path)}
            isFirst={manualOrder ? i === 0 : true}
            isLast={manualOrder ? i === data.papers.length - 1 : true}
          />
        ))}
    </div>
  )
}
