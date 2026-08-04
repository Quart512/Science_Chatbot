import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listNotes, saveNote } from '../api/notes'
import { NoteRow } from './NoteRow'
import './Notes.css'

export function Notes() {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['notes'],
    queryFn: listNotes,
  })

  const createMutation = useMutation({
    mutationFn: () => saveNote({ title, text }),
    onSuccess: () => {
      setTitle('')
      setText('')
      queryClient.invalidateQueries({ queryKey: ['notes'] })
    },
  })

  return (
    <div>
      <h1>📝 지식 노트</h1>

      <details>
        <summary>새 노트 작성</summary>
        <form
          className="note-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (!text) return
            createMutation.mutate()
          }}
        >
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="제목" />
          <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="본문" />
          <button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? '저장 중...' : '저장'}
          </button>
        </form>
      </details>

      <hr />

      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="note-error">조회 실패: {(error as Error).message}</p>}
      {data && data.notes.length === 0 && <p>작성된 노트가 없습니다.</p>}
      {data && data.notes.map((n) => <NoteRow key={n.id} note={n} />)}
    </div>
  )
}
