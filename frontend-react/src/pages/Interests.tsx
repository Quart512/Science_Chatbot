import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listInterests, saveInterest, type InterestDraftResponse } from '../api/interests'
import { InterestCard } from './InterestCard'
import { InterestIcon } from '../components/NavIcons'
import './Interests.css'

// 챗 패널의 "이 대화를 관심사로 등록" 버튼이 draft를 라우터 state로 실어 보낸다
// (frontend/views/chat.py의 session_state.interest_draft와 같은 역할, RoadMap
// "프론트 스택 전환" 참고 — Streamlit의 st.session_state 프리필 패턴을 React Router의
// navigate state로 옮김).
export function Interests() {
  const queryClient = useQueryClient()
  const location = useLocation()
  const draft = location.state as InterestDraftResponse | undefined

  const [open, setOpen] = useState(Boolean(draft))
  const [title, setTitle] = useState(draft?.title ?? '')
  const [lookingFor, setLookingFor] = useState(draft?.looking_for ?? '')
  const [alreadyKnown, setAlreadyKnown] = useState(draft?.already_known ?? '')
  const [excludedTopics, setExcludedTopics] = useState(draft?.excluded_topics ?? '')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['interests'],
    queryFn: listInterests,
  })

  const createMutation = useMutation({
    mutationFn: () => saveInterest({ title, looking_for: lookingFor, already_known: alreadyKnown, excluded_topics: excludedTopics }),
    onSuccess: () => {
      setTitle('')
      setLookingFor('')
      setAlreadyKnown('')
      setExcludedTopics('')
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ['interests'] })
    },
  })

  return (
    <div>
      <h1><InterestIcon size={22} /> 관심사</h1>

      <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary>새 관심사 만들기</summary>
        {draft?.warning && <p className="interest-card-error">{draft.warning}</p>}
        <form
          className="interest-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (!title) return
            createMutation.mutate()
          }}
        >
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="제목" />
          <textarea value={lookingFor} onChange={(e) => setLookingFor(e.target.value)} placeholder="찾는 것" />
          <textarea value={alreadyKnown} onChange={(e) => setAlreadyKnown(e.target.value)} placeholder="이미 아는 것" />
          <input value={excludedTopics} onChange={(e) => setExcludedTopics(e.target.value)} placeholder="제외할 주제" />
          <button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? '만드는 중...' : '만들기'}
          </button>
        </form>
        {createMutation.isError && (
          <p className="interest-card-error">생성 실패: {(createMutation.error as Error).message}</p>
        )}
      </details>

      <hr />

      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="interest-card-error">관심사 조회 실패: {(error as Error).message}</p>}
      {data && data.interests.length === 0 && <p>등록된 관심사가 없습니다.</p>}
      {data &&
        data.interests.map((interest, i) => (
          <InterestCard
            key={interest.id}
            interest={interest}
            isFirst={i === 0}
            isLast={i === data.interests.length - 1}
          />
        ))}
    </div>
  )
}
