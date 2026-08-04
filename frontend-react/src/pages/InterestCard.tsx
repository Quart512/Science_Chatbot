import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteInterest,
  listInterestPapers,
  refreshInterest,
  saveInterest,
  searchInterest,
  type Interest,
  type RecommendResult,
} from '../api/interests'

const SEARCH_PAGE_SIZE = 5 // paper_recommend.recommend_for_interest()의 max_results 기본값과 맞춤

const STATUS_LABELS: Record<string, string> = { recommended: '추천됨', owned: '보유', dismissed: '기각됨' }

// EquipmentRow.tsx와 같은 인라인 편집 패턴(08-04) — "수정"을 누르면 그 자리에서 바로
// 텍스트박스로 바뀌고 버튼이 "저장"으로 바뀐다. draft는 "수정" 클릭 순간에 interest에서
// 다시 채워서 편집 중 다른 카드 조작으로 인한 리페치와 충돌하지 않는다.
export function InterestCard({ interest }: { interest: Interest }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(interest.title)
  const [editLookingFor, setEditLookingFor] = useState(interest.looking_for)
  const [editAlreadyKnown, setEditAlreadyKnown] = useState(interest.already_known)
  const [editExcluded, setEditExcluded] = useState(interest.excluded_topics)

  // 검색 결과는 이번 세션 임시(chat.py의 st.session_state[results_key]와 같은 성격) —
  // 서버에 저장 안 하고 컴포넌트 로컬 상태로만 들고 있는다.
  const [results, setResults] = useState<RecommendResult[] | null>(null)
  const [offset, setOffset] = useState(0)

  const papersQuery = useQuery({
    queryKey: ['interest-papers', interest.id],
    queryFn: () => listInterestPapers(interest.id),
  })

  const editMutation = useMutation({
    mutationFn: async () => {
      await saveInterest({
        title: editTitle,
        looking_for: editLookingFor,
        already_known: editAlreadyKnown,
        excluded_topics: editExcluded,
        update_existing_id: interest.id,
      })
      // 관심사가 바뀌면 기존 후보를 버리지 않고 새 기준으로 재스크리닝(refresh_for_interest 참고)
      return refreshInterest(interest.id, results ?? [])
    },
    onSuccess: (data) => {
      setResults(data.recommended)
      setOffset(SEARCH_PAGE_SIZE)
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['interests'] })
      queryClient.invalidateQueries({ queryKey: ['interest-papers', interest.id] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteInterest(interest.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['interests'] }),
  })

  const searchMutation = useMutation({
    mutationFn: () => searchInterest(interest.id, results ? offset : 0),
    onSuccess: (data) => {
      if (results) {
        const combined = [...results, ...data.recommended]
        combined.sort((a, b) => Number(a.is_relevant === b.is_relevant ? 0 : a.is_relevant ? -1 : 1))
        setResults(combined)
        setOffset((o) => o + SEARCH_PAGE_SIZE)
      } else {
        setResults(data.recommended)
        setOffset(SEARCH_PAGE_SIZE)
      }
    },
  })

  function startEditing() {
    setEditTitle(interest.title)
    setEditLookingFor(interest.looking_for)
    setEditAlreadyKnown(interest.already_known)
    setEditExcluded(interest.excluded_topics)
    setEditing(true)
  }

  if (editing) {
    return (
      <div className="interest-card">
        <form
          className="interest-form"
          onSubmit={(e) => {
            e.preventDefault()
            editMutation.mutate()
          }}
        >
          <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} placeholder="제목" />
          <textarea value={editLookingFor} onChange={(e) => setEditLookingFor(e.target.value)} placeholder="찾는 것" />
          <textarea
            value={editAlreadyKnown}
            onChange={(e) => setEditAlreadyKnown(e.target.value)}
            placeholder="이미 아는 것"
          />
          <input value={editExcluded} onChange={(e) => setEditExcluded(e.target.value)} placeholder="제외할 주제" />
          <div className="interest-card-actions">
            <div className="interest-card-actions-left">
              <button type="submit" disabled={editMutation.isPending}>
                {editMutation.isPending ? '저장 중... (재검색까지 진행)' : '저장'}
              </button>
              <button type="button" onClick={() => setEditing(false)}>
                취소
              </button>
            </div>
            <button type="button" className="interest-card-delete" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
              삭제
            </button>
          </div>
        </form>
      </div>
    )
  }

  const papers = papersQuery.data?.papers ?? []

  return (
    <div className="interest-card">
      <h3>{interest.title}</h3>
      {interest.looking_for && <p className="interest-card-meta">찾는 것: {interest.looking_for}</p>}

      {papers.length > 0 && (
        <details className="interest-card-papers">
          <summary>보유·추천 논문 ({papers.length})</summary>
          {papers.map((p) => (
            <div key={p.paper_id} className="interest-card-paper">
              <strong>{p.title || p.paper_id}</strong> — {STATUS_LABELS[p.status] ?? p.status ?? '상태 없음'}
              {p.reasoning && <p className="interest-card-meta">{p.reasoning}</p>}
            </div>
          ))}
        </details>
      )}

      <div className="interest-card-actions">
        <div className="interest-card-actions-left">
          <button onClick={() => searchMutation.mutate()} disabled={searchMutation.isPending}>
            {searchMutation.isPending ? '검색 중...' : results ? '추가 검색' : '지금 검색'}
          </button>
          <button onClick={startEditing}>수정</button>
        </div>
        <button className="interest-card-delete" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
          삭제
        </button>
      </div>

      {searchMutation.isError && (
        <p className="interest-card-error">검색 실패: {(searchMutation.error as Error).message}</p>
      )}

      {results && (
        results.length === 0 ? (
          <p className="interest-card-meta">검색된 후보가 없습니다.</p>
        ) : (
          <table className="interest-results-table">
            <thead>
              <tr>
                <th>순위</th>
                <th>제목</th>
                <th>근거</th>
                <th>peer review</th>
                <th>연도</th>
                <th>인용수</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={r.paper_id}>
                  <td>{i + 1}</td>
                  <td>{r.title}</td>
                  <td>{r.reasoning}</td>
                  <td>{r.peer_reviewed ? 'O' : 'X'}</td>
                  <td>{r.year}</td>
                  <td>{r.citation_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </div>
  )
}
