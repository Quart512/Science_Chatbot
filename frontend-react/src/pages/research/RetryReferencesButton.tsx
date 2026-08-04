import { useMutation, useQueryClient } from '@tanstack/react-query'
import { retryResearchReferences } from '../../api/research'

interface Props {
  threadId: string
  onRetried: () => void
}

// 참고문헌만 독립 재시도(08-04 후속, Part B — RoadMap "참고문헌만 재검색 + 실패 사유
// 표시") — 그 단계 산출물(가설·설계 등)은 안 건드리고 참고문헌 검색만 다시 돈다.
// tip에서만 동작(백엔드가 tip만 지원 — 단순 경로부터, Research.tsx가 isTip일 때만 렌더링).
export function RetryReferencesButton({ threadId, onRetried }: Props) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => retryResearchReferences(threadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-history', threadId] })
      onRetried()
    },
  })

  return (
    <div className="research-retry-references">
      <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
        {mutation.isPending ? '재검색 중...' : '🔁 참고문헌만 다시 찾기'}
      </button>
      {mutation.isError && <p className="research-warning">재검색 실패: {(mutation.error as Error).message}</p>}
    </div>
  )
}
