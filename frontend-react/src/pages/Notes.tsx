import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listNotes, saveNote } from '../api/notes'
import { NoteRow } from './NoteRow'
import './Notes.css'

export function Notes() {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [search, setSearch] = useState('')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['notes', search],
    queryFn: () => listNotes(search || undefined),
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

      <input
        type="search"
        className="note-search"
        placeholder="제목으로 검색"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {/* 검색 중엔 순서 버튼을 끈다 — Papers.tsx와 같은 이유(필터링된 부분집합
          안에서 "이웃"을 옮기면 전체 순서와 어긋나 혼란만 준다). */}
      {search !== '' && (
        <p className="library-hint">검색 중에는 순서 버튼이 꺼집니다 — 검색어를 지우면 다시 켜집니다.</p>
      )}
      {isLoading && <p>불러오는 중...</p>}
      {isError && <p className="note-error">조회 실패: {(error as Error).message}</p>}
      {data && data.notes.length === 0 && <p>{search ? '검색 결과가 없습니다.' : '작성된 노트가 없습니다.'}</p>}
      {data &&
        data.notes.map((n, i) => (
          <NoteRow
            key={n.id}
            note={n}
            isFirst={search === '' ? i === 0 : true}
            isLast={search === '' ? i === data.notes.length - 1 : true}
          />
        ))}
    </div>
  )
}
