import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteNote, saveNote, type Note } from '../api/notes'

// EquipmentRow.tsx와 같은 인라인 편집 패턴(08-04) — "수정" 클릭 순간에 draft를
// note에서 다시 채워서, 그 사이 리페치가 와도 편집 중인 내용과 충돌하지 않는다.
export function NoteRow({ note }: { note: Note }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(note.title)
  const [text, setText] = useState(note.text)

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

  const preview = note.text.length > 200 ? `${note.text.slice(0, 200)}...` : note.text

  return (
    <div className="note-row">
      <h3>{note.title || '(제목 없음)'}</h3>
      <p className="note-row-preview">{preview}</p>

      <div className="note-row-actions">
        <div className="note-row-actions-left">
          <button onClick={startEditing}>수정</button>
        </div>
        <button className="note-delete" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
          삭제
        </button>
      </div>
    </div>
  )
}
