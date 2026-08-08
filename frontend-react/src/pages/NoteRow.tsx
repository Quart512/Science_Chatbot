import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteNote, moveNote, saveNote, type Note } from '../api/notes'
import { FullscreenModal } from '../components/FullscreenModal'
import { ReorderButtons } from '../components/ReorderButtons'

const PREVIEW_CHAR_LIMIT = 200
// 글자수만 보면 줄바꿈이 많은 노트(짧은 줄 수십 개)를 놓친다 — 총 글자수는
// 200자 미만이어도 줄이 많으면 미리보기 박스가 세로로 한없이 길어진다(사용자 실측).
const PREVIEW_LINE_LIMIT = 8

// EquipmentRow.tsx와 같은 인라인 편집 패턴(08-04) — "수정" 클릭 순간에 draft를
// note에서 다시 채워서, 그 사이 리페치가 와도 편집 중인 내용과 충돌하지 않는다.
export function NoteRow({ note, isFirst, isLast }: { note: Note; isFirst: boolean; isLast: boolean }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(note.title)
  const [text, setText] = useState(note.text)
  const [fullView, setFullView] = useState(false)

  const saveMutation = useMutation({
    mutationFn: () => saveNote({ title, text, update_existing_id: note.id }),
    onSuccess: () => {
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['notes'] })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: () => deleteNote(note.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notes'] }),
  })
  const moveMutation = useMutation({
    mutationFn: (direction: 'up' | 'down') => moveNote(note.id, direction),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notes'] }),
  })

  function startEditing() {
    setTitle(note.title)
    setText(note.text)
    setEditing(true)
  }

  if (editing) {
    return (
      <div className="note-row">
        <form
          className="note-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (!text) return
            saveMutation.mutate()
          }}
        >
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="제목" />
          <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="본문" />
          <div className="note-row-actions">
            <div className="note-row-actions-left">
              <button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? '저장 중...' : '저장'}
              </button>
              <button type="button" onClick={() => setEditing(false)}>
                취소
              </button>
            </div>
            <button type="button" className="note-delete" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
              삭제
            </button>
          </div>
        </form>
      </div>
    )
  }

  const lines = note.text.split('\n')
  const truncatedByLines = lines.length > PREVIEW_LINE_LIMIT
  const byLines = truncatedByLines ? lines.slice(0, PREVIEW_LINE_LIMIT).join('\n') : note.text
  const truncated = truncatedByLines || byLines.length > PREVIEW_CHAR_LIMIT
  const preview = truncated ? `${byLines.slice(0, PREVIEW_CHAR_LIMIT)}...` : byLines

  return (
    <div className="library-reorder-row">
      <ReorderButtons
        isFirst={isFirst}
        isLast={isLast}
        pending={moveMutation.isPending}
        onMoveUp={() => moveMutation.mutate('up')}
        onMoveDown={() => moveMutation.mutate('down')}
      />
      <div className="note-row">
        <h3>{note.title || '(제목 없음)'}</h3>
        <p className="note-row-preview">{preview}</p>
        {/* 200자 넘는 노트는 수정 모드에 들어가야만 전문을 볼 수 있었다(사용자 지적) —
            읽기 전용 전문 뷰어를 따로 둔다. 짧은 노트는 preview가 이미 전문이라 버튼 자체가
            불필요. */}
        {truncated && (
          <button type="button" className="note-row-expand" onClick={() => setFullView(true)}>
            전문 보기
          </button>
        )}

        <div className="note-row-actions">
          <div className="note-row-actions-left">
            <button onClick={startEditing}>수정</button>
          </div>
          <button className="note-delete" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
            삭제
          </button>
        </div>

        {fullView && (
          <FullscreenModal title={note.title || '(제목 없음)'} onClose={() => setFullView(false)}>
            <div className="note-row-fullview">{note.text}</div>
          </FullscreenModal>
        )}
      </div>
    </div>
  )
}
