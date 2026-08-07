import { useState } from 'react'
import type { TraceStep } from '../api/chat'
import './StreamProgress.css'

// 스트리밍 진행 로그를 스텝별 접이식 목록으로 보여준다(08-07, RoadMap "스트리밍 로그
// 가독성" ①②). graph.py가 이제 trace를 TraceStep 구조로 보내므로(chat.ts 참고) 프론트는
// 정규식 파싱 없이 label/detail을 그대로 쓴다 — 기본은 라벨 한 줄만, 클릭하면 detail이
// 펼쳐진다. ChatPanel(오른쪽 패널)·Chat(왼쪽 화면) 둘 다 같은 진행 로그 렌더링이 필요해서
// 공용 컴포넌트로 뽑았다(두 번째 호출부가 실제로 생긴 시점에 뽑는 것 — RoadMap "단순 경로부터").
//
// live: 지금 스트리밍 중인지(⏳) vs 지나간 턴을 사후 열람 중인지(✓/⚠️) — final_answer가
// comment와 함께 trace도 AIMessage.additional_kwargs에 심어 체크포인트에 남기므로(main.py),
// 새로고침 후에도 과거 메시지에 이 컴포넌트를 그대로 재사용한다(live={false}로).
export function StreamProgress({ steps, live = true }: { steps: TraceStep[]; live?: boolean }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  if (steps.length === 0) {
    return live ? <div className="stream-progress-empty">⏳ 진행 중...</div> : null
  }

  return (
    <div className="stream-progress">
      {steps.map((step, i) => {
        const open = openIndex === i
        return (
          <div key={i} className={`stream-progress-step${step.ok ? '' : ' stream-progress-step-error'}`}>
            <button
              type="button"
              className="stream-progress-step-header"
              onClick={() => setOpenIndex(open ? null : i)}
            >
              <span className="stream-progress-step-toggle">{open ? '▾' : '▸'}</span>
              <span className="stream-progress-step-label">
                {live ? '⏳' : step.ok ? '✓' : '⚠️'} {step.label}
              </span>
            </button>
            {open && <div className="stream-progress-step-detail">{step.detail}</div>}
          </div>
        )
      })}
    </div>
  )
}
