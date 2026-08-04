import { useState } from 'react'
import type { HistoryEntry } from '../../api/research'
import { STAGES, STAGE_LABELS, cellStatus, type NextOption } from './constants'

const ROW_HEIGHT = 44
const LANE_X = 14

interface Props {
  history: HistoryEntry[] // 오래된 것부터, 마지막이 tip
  selectedCheckpointId: string
  onSelect: (checkpointId: string) => void
  nextOpts: NextOption[] // tip에서 갈 수 있는 곳 — 브랜치형 타임라인 하단에 갈래로 표시
}

// RoadMap "연구 워크플로우 — 타임라인·체크 결합(브랜치형)" 설계 노트의 화면 모델 그대로.
// 예전엔 위쪽 완료체크 타임라인(research-timeline)과 아래쪽 체크포인트 탭 목록
// (research-tabs)이 분리돼 있었는데, 이 컴포넌트가 하나로 합친다: 접으면 tip 한 줄
// (fresh/계승/미진행 3색)만, 펼치면 과거 행이 위로 쌓이며 git graph처럼 세로선으로
// 계보가 이어진다. 세로선은 parent_config가 아니라 백엔드의 research_branches
// 사이드테이블(branched_from_checkpoint_id)에서 얻는다 — 이유는 api/research.ts의
// HistoryEntry 주석 참고.
export function BranchTimeline({ history, selectedCheckpointId, onSelect, nextOpts }: Props) {
  const [expanded, setExpanded] = useState(false)
  const tip = history[history.length - 1]
  const rows = expanded ? history : [tip]

  const indexById = new Map(history.map((e, i) => [e.checkpoint_id, i]))
  const rowIndexById = new Map(rows.map((e, i) => [e.checkpoint_id, i]))

  // 각 행이 어느 행에서 이어지는지 — branched_from_checkpoint_id가 있으면 그 행,
  // 없으면 바로 위(직전) 행이 기본 부모다(선형 진행). 펼쳤을 때만 그린다 — 접힌
  // 상태는 행이 하나뿐이라 이을 게 없다.
  const connectors: Array<{ fromY: number; toY: number; isBranch: boolean }> = []
  if (expanded) {
    for (let i = 1; i < rows.length; i++) {
      const entry = rows[i]
      const historyIdx = indexById.get(entry.checkpoint_id) ?? i
      const branchSourceId = entry.branched_from_checkpoint_id
      const sourceHistoryIdx = branchSourceId !== null ? indexById.get(branchSourceId) : historyIdx - 1
      const sourceRowIdx = sourceHistoryIdx !== undefined ? rowIndexById.get(history[sourceHistoryIdx].checkpoint_id) : i - 1
      const fromRow = sourceRowIdx ?? i - 1
      connectors.push({
        fromY: fromRow * ROW_HEIGHT + ROW_HEIGHT / 2,
        toY: i * ROW_HEIGHT + ROW_HEIGHT / 2,
        isBranch: fromRow !== i - 1,
      })
    }
  }

  return (
    <div className="research-branch-timeline">
      <button type="button" className="research-branch-toggle" onClick={() => setExpanded((v) => !v)}>
        {expanded ? '▾ 접기' : `▸ 펼치기 (기록 ${history.length}개)`}
      </button>

      <div className="research-branch-rows" style={{ height: rows.length * ROW_HEIGHT }}>
        {expanded && (
          <svg className="research-branch-svg" width={LANE_X + 16} height={rows.length * ROW_HEIGHT}>
            {connectors.map((c, i) =>
              c.isBranch ? (
                <path
                  key={i}
                  className="research-branch-line-branch"
                  d={`M ${LANE_X} ${c.fromY} C ${LANE_X - 14} ${(c.fromY + c.toY) / 2}, ${LANE_X - 14} ${(c.fromY + c.toY) / 2}, ${LANE_X} ${c.toY}`}
                  fill="none"
                />
              ) : (
                <line key={i} className="research-branch-line" x1={LANE_X} y1={c.fromY} x2={LANE_X} y2={c.toY} />
              )
            )}
            {rows.map((_, i) => (
              <circle key={i} className="research-branch-dot" cx={LANE_X} cy={i * ROW_HEIGHT + ROW_HEIGHT / 2} r={4} />
            ))}
          </svg>
        )}

        {rows.map((entry) => {
          const isTip = entry.checkpoint_id === tip.checkpoint_id
          const ts = entry.created_at ? entry.created_at.slice(11, 16) : ''
          return (
            <button
              type="button"
              key={entry.checkpoint_id}
              className={`research-branch-row ${entry.checkpoint_id === selectedCheckpointId ? 'research-branch-row-active' : ''}`}
              style={{ marginLeft: expanded ? LANE_X + 16 : 0 }}
              onClick={() => onSelect(entry.checkpoint_id)}
            >
              <span className="research-branch-row-label">
                {expanded ? `${ts} · ${STAGE_LABELS[entry.stage] ?? entry.stage}` : '현재 상태'}
                {isTip && expanded && ' (현재)'}
              </span>
              <span className="research-branch-cells">
                {STAGES.map(([stageKey, label]) => (
                  <span
                    key={stageKey}
                    className={`research-branch-cell research-branch-cell-${cellStatus(entry.values.stage, stageKey)}`}
                  >
                    {label}
                  </span>
                ))}
              </span>
            </button>
          )
        })}
      </div>

      {nextOpts.length > 0 && (
        <div className="research-branch-future">
          <span className="research-branch-future-stem" />
          <span className="research-branch-future-label">{STAGE_LABELS[tip.values.stage]}에서 갈 수 있는 곳</span>
          <div className="research-branch-future-options">
            {nextOpts.map((opt) => (
              <span
                key={`${opt.target}_${opt.label}`}
                className={`research-branch-future-chip ${opt.recommended ? 'research-branch-future-chip-recommended' : ''}`}
              >
                → {opt.label}
                {opt.recommended && ' [추천]'}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
