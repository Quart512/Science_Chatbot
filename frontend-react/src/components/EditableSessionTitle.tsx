import { useEffect, useRef, useState } from 'react'
import './EditableSessionTitle.css'

interface Props {
  title: string
  onOpen: () => void
  onRename: (newTitle: string) => void
  onClose: () => void
  renamePending?: boolean
  closePending?: boolean
}

// 세션 카드(챗봇/연구 워크플로우, 사이드바 목록·본문 카드 화면 4곳 공용) 제목 행 —
// 08-06 화면 개선. 예전엔 "수정" 누르면 아래 별도 폼(입력창+저장/취소 버튼)이
// 펼쳐졌는데, 이제 제목 자리 자체가 바로 입력창으로 바뀐다(Enter나 다른 곳 클릭=
// 반영, Esc=취소). 연필(✎)·닫기(✕) 아이콘은 평소엔 투명하고 이 행에 마우스를
// 올리거나(hover) 키보드로 포커스가 들어왔을 때만(focus-within, 접근성) 보인다.
//
// Esc 취소 우선순위 메모(사용자 지시, RoadMap "스트리밍 중 인터럽트" 항목 — 아직
// 미착수): 나중에 챗봇에 "Esc로 스트리밍 취소" 기능이 생기면, 지금 이 인라인 편집의
// Esc(이름 수정 취소)가 그 스트리밍 취소보다 먼저 처리돼야 한다. 여기서
// `stopPropagation()`을 호출해두는 이유가 그것 — 입력창에 포커스가 있는 동안의
// Esc는 이 컴포넌트가 먼저 가로채고, 상위(예: 미래의 window keydown 리스너)로
// 안 넘어간다.
export function EditableSessionTitle({ title, onOpen, onRename, onClose, renamePending, closePending }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(title)
  const cancelledRef = useRef(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [editing])

  function startEditing(e: React.MouseEvent) {
    e.stopPropagation()
    setDraft(title)
    setEditing(true)
  }

  function commit() {
    // Esc로 취소한 직후 input이 blur되면서 onBlur(commit)도 같이 불릴 수 있어
    // (DOM에서 포커스가 옮겨가는 순간 브라우저가 blur를 낸다) 커밋을 건너뛴다.
    if (cancelledRef.current) {
      cancelledRef.current = false
      return
    }
    setEditing(false)
    const trimmed = draft.trim()
    if (trimmed && trimmed !== title) onRename(trimmed)
  }

  function cancel() {
    cancelledRef.current = true
    setDraft(title)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="session-title-row">
        <input
          ref={inputRef}
          className="session-title-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          // 08-06 — 카드 전체가 클릭 가능해지면서(ChatSessionNav/ResearchSessionNav 참고)
          // 이 입력창 안을 클릭(커서 이동 등)해도 부모로 버블링돼 onSelect가 발동,
          // 수정 중에 다른 세션으로 이동해버리는 걸 막는다.
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              commit()
            } else if (e.key === 'Escape') {
              e.stopPropagation()
              cancel()
            }
          }}
        />
      </div>
    )
  }

  return (
    <div className="session-title-row">
      <button type="button" className="session-title-open" onClick={onOpen}>
        {title}
      </button>
      <span className="session-title-icons">
        <button
          type="button"
          className="session-icon-btn"
          title="이름 수정"
          aria-label="이름 수정"
          onClick={startEditing}
          disabled={renamePending}
        >
          ✎
        </button>
        <button
          type="button"
          className="session-icon-btn session-icon-btn-close"
          title="닫기"
          aria-label="닫기"
          onClick={(e) => {
            e.stopPropagation()
            onClose()
          }}
          disabled={closePending}
        >
          ✕
        </button>
      </span>
    </div>
  )
}
