import './ReorderButtons.css'

interface Props {
  onMoveUp: () => void
  onMoveDown: () => void
  isFirst: boolean
  isLast: boolean
  pending?: boolean
}

// 라이브러리 4곳(관심사·논문·실험도구·지식노트) 공용 위/아래 순서 버튼 — 드래그 대신
// 버튼을 고른 이유는 새 프론트 의존성이 필요 없고 접근성도 기본으로 챙겨져서(08-06,
// 사용자 결정). 경계(맨 위/맨 아래)에서는 버튼 자체를 disabled로 둬서, 눌러도 아무
// 일도 안 일어나는 게 아니라 애초에 누를 수 없게 한다.
export function ReorderButtons({ onMoveUp, onMoveDown, isFirst, isLast, pending }: Props) {
  return (
    <div className="reorder-buttons">
      <button type="button" onClick={onMoveUp} disabled={isFirst || pending} aria-label="위로 이동" title="위로 이동">
        ▲
      </button>
      <button type="button" onClick={onMoveDown} disabled={isLast || pending} aria-label="아래로 이동" title="아래로 이동">
        ▼
      </button>
    </div>
  )
}
