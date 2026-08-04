import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './api/client'

interface Interest {
  id: number
  title: string
}

// Phase 0 스캐폴딩 확인용 — CORS+API 클라이언트 배관이 실제로 되는지만 본다.
// 셸(사이드바)+챗 화면이 다음 단계(RoadMap "프론트 스택 전환" 설계 노트 참고).
function App() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['interests'],
    queryFn: () => apiFetch<{ interests: Interest[] }>('/interests'),
  })

  return (
    <main style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>연구 워크플로우 — React 프론트 (착수)</h1>
      {isLoading && <p>백엔드에 연결하는 중...</p>}
      {isError && <p style={{ color: 'crimson' }}>연결 실패: {(error as Error).message}</p>}
      {data && (
        <p style={{ color: 'seagreen' }}>
          백엔드 연결 확인됨 — 관심사 {data.interests.length}건 조회
        </p>
      )}
    </main>
  )
}

export default App
