import { useEffect, type ReactNode } from 'react'
import './FullscreenModal.css'

interface Props {
  title: string
  onClose: () => void
  children: ReactNode
}

// PaperRow.tsx의 PDF 전체화면 뷰어에서 뽑아낸 공용 오버레이 — 두 번째 호출부(지식
// 노트 전문 뷰어)가 생기는 시점에 추출("두 번째 호출부가 실제로 생기는 지금 뽑는다"
// 원칙, useChatThread 분리 때와 같은 이유). Esc는 window 레벨 리스너로 처리한다 —
// EditableSessionTitle.tsx의 기존 컨벤션(입력창 포커스 중 Esc는 그 입력창이
// stopPropagation으로 먼저 가로채 로컬에서 끝남)과 겹치지 않는다: 그쪽은 특정
// input에 포커스가 있을 때만 반응하는 로컬 핸들러라 여기 켜져 있는 동안에도 우선
// 처리되고, 이 window 리스너는 더 구체적인 핸들러가 없을 때만 열려있는 모달을
// 닫는 최후순위로 동작한다.
export function FullscreenModal({ title, onClose, children }: Props) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div className="fullscreen-modal-overlay" onClick={onClose}>
      <div className="fullscreen-modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="fullscreen-modal-header">
          <span>{title}</span>
          <button type="button" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
