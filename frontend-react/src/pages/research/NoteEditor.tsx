import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { saveResearchNote } from '../../api/research'

interface Props {
  threadId: string
  checkpointId: string
  initialNote: string
}

// 단계별 메모(08-04 후속, RoadMap "타임라인·체크 결합(브랜치형)" 설계 노트 §단계별
// 메모, 방식 B) — DraftEditor와 달리 tip 제한이 없다: 지금 보고 있는 체크포인트가
// 과거 시점이어도(BranchTimeline에서 행을 클릭해 이동) 그 시점 자체에 메모를 남기고
// 고칠 수 있다(research_notes.py가 체크포인트를 안 건드리는 별도 테이블이라 가능).
// key={checkpointId}로 호출부에서 렌더링 — 다른 체크포인트로 옮기면 draft가 그
// 시점의 저장된 메모로 다시 초기화된다(DraftEditor의 key={checkpointId}와 같은 이유).
export function NoteEditor({ threadId, checkpointId, initialNote }: Props) {
  const queryClient = useQueryClient()
  const [note, setNote] = useState(initialNote)

  const mutation = useMutation({
    mutationFn: () => saveResearchNote(threadId, checkpointId, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-history', threadId] })
    },
  })

  const dirty = note !== initialNote

  return (
    <div className="research-note-editor">
      <label className="research-caption">📝 메모</label>
      <textarea
        className="research-textarea"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="이 시점에 대한 메모(장비 주의사항, 다음에 시도할 것 등)"
      />
      <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending || !dirty}>
        {mutation.isPending ? '저장 중...' : '메모 저장'}
      </button>
      {mutation.isError && <p className="research-warning">저장 실패: {(mutation.error as Error).message}</p>}
    </div>
  )
}
