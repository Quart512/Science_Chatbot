import { apiFetch } from './client'

export interface Note {
  id: number
  title: string
  text: string
}

export interface SaveNoteBody {
  title?: string
  text?: string
  update_existing_id?: number
}

export function listNotes(q?: string) {
  const query = q ? `?q=${encodeURIComponent(q)}` : ''
  return apiFetch<{ notes: Note[] }>(`/notes${query}`)
}

export function saveNote(body: SaveNoteBody) {
  return apiFetch<{ note_id: number; action: string }>('/notes', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function deleteNote(id: number) {
  return apiFetch<{ note_id: number; action: string }>(`/notes/${id}`, { method: 'DELETE' })
}

export function moveNote(id: number, direction: 'up' | 'down') {
  return apiFetch<{ note_id: number; moved: boolean }>(`/notes/${id}/move?direction=${direction}`, {
    method: 'POST',
  })
}
