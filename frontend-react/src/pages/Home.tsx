import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'

interface Interest {
  id: number
  title: string
}

// 자리표시 홈 — 논문/관심사/실험도구/지식노트/연구 워크플로우 화면이 순차 이관되면
// 그 화면들의 네비게이션 진입점이 될 자리. 지금은 Phase 0의 연결 확인 그대로 둔다.
export function Home() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['interests'],
    queryFn: () => apiFetch<{ interests: Interest[] }>('/interests'),
  })

  return (
    <div>
      <h1>연구 워크플로우 — React 프론트 (이관 진행 중)</h1>
      {isLoading && <p>백엔드에 연결하는 중...</p>}
      {isError && <p style={{ color: 'crimson' }}>연결 실패: {(error as Error).message}</p>}
      {data && (
        <p style={{ color: 'seagreen' }}>
          백엔드 연결 확인됨 — 관심사 {data.interests.length}건 조회
        </p>
      )}
      <p>오른쪽 챗 패널은 이 화면과 별개로 항상 쓸 수 있습니다.</p>
    </div>
  )
}
