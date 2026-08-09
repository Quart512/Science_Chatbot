import { useQuery } from '@tanstack/react-query'
import { getEmbeddingStatus, type EmbeddingStatus } from '../api/settings'

// 첫 실행 시 bge-m3(약 2.1GB) 준비 진행률 폴링(08-09).
//
// 두 곳(첫 실행 안내창·화면 하단 배너)이 같이 쓴다 — queryKey가 같으므로 react-query가
// 요청을 하나로 합쳐준다(컴포넌트마다 따로 폴링하지 않는다).
//
// ready가 되면 폴링을 멈춘다. 한번 준비된 모델이 다시 안 준비된 상태로 돌아갈 일이
// 없어서, 계속 물어봐야 상태가 안 바뀐다. failed는 계속 폴링한다 — 다음 임베딩 요청이
// 재시도해서 성공하면 그걸 화면이 따라가야 한다(embeddings.load()가 실패 후 재시도를
// 허용하도록 만들어져 있다).
export function useEmbeddingStatus() {
  return useQuery<EmbeddingStatus>({
    queryKey: ['embedding-status'],
    queryFn: getEmbeddingStatus,
    refetchInterval: (query) => (query.state.data?.state === 'ready' ? false : 2000),
  })
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)}GB`
  if (bytes >= 1_000_000) return `${Math.round(bytes / 1_000_000)}MB`
  return `${Math.round(bytes / 1_000)}KB`
}
