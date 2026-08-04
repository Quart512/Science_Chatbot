import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateResearchDraft, type ResearchState } from '../../api/research'

const FIELDS = [
  ['title', '제목'],
  ['abstract', '초록'],
  ['introduction', '서론'],
  ['methods', '방법'],
  ['results', '결과'],
  ['discussion', '고찰'],
] as const

// frontend/views/research.py의 "초안 수정" expander와 같은 계약 — writing 단계이면서
// tip을 보고 있을 때만 렌더링(호출부에서 조건 검사). 원문(마커 그대로)을 보여줘야
// 저장 시 [CITE:paper_id]가 안 깨진다.
export function DraftEditor({ threadId, values, checkpointId }: { threadId: string; values: ResearchState; checkpointId: string }) {
  const queryClient = useQueryClient()
  const [fields, setFields] = useState<Record<string, string>>(
    Object.fromEntries(FIELDS.map(([key]) => [key, values[key] as string])),
  )

  const mutation = useMutation({
    mutationFn: () => updateResearchDraft(threadId, fields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-history', threadId] })
    },
  })

  return (
    <details>
      <summary>초안 수정</summary>
      <p className="research-caption">
        [CITE:논문id] 표시는 인용 마커입니다 — 위 본문엔 서지 형식으로 바뀌어 보이지만 여기선 원문 그대로이니 지우지 마세요.
      </p>
      <form
        key={checkpointId}
        onSubmit={(e) => {
          e.preventDefault()
          mutation.mutate()
        }}
      >
        {FIELDS.map(([key, label]) => (
          <div key={key}>
            <label className="research-caption">{label}</label>
            {key === 'title' ? (
              <input
                className="research-input"
                value={fields[key]}
                onChange={(e) => setFields((f) => ({ ...f, [key]: e.target.value }))}
              />
            ) : (
              <textarea
                className="research-textarea"
                value={fields[key]}
                onChange={(e) => setFields((f) => ({ ...f, [key]: e.target.value }))}
              />
            )}
          </div>
        ))}
        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? '저장 중...' : '저장'}
        </button>
      </form>
    </details>
  )
}
