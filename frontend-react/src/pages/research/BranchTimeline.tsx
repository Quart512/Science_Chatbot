import { useState } from 'react'
import type { HistoryEntry } from '../../api/research'
import { STAGES, STAGE_LABELS, cellStatus } from './constants'

const ROW_HEIGHT = 44
// 08-06 화면 개선 ③④ — 목업으로 먼 분기(여러 행을 건너뛰는 경우)를 확인하며 조정한 값.
// 곡선이 왼쪽으로 부푸는 정도(bulge)를 세로 거리에 비례하게 해서 가까운 분기는 아담하게,
// 먼 분기는 더 넓게 그린다(상한 BULGE_MAX로 무한정 안 커지게). LANE_X는 BULGE_MAX보다
// 넉넉히 커야 곡선이 SVG 왼쪽 경계 밖으로 안 나간다 — 처음 좁게(14px 고정) 했을 때
// 실제로 밖으로 튀어나가는 걸 목업에서 발견해서 고쳤다.
const LANE_X = 56
const BULGE_MIN = 14
const BULGE_MAX = 44
const LANE_WIDTH = LANE_X + 14

interface Props {
  history: HistoryEntry[] // 오래된 것부터, 마지막이 tip
  selectedCheckpointId: string
  onSelect: (checkpointId: string) => void
}

// RoadMap "연구 워크플로우 — 타임라인·체크 결합(브랜치형)" 설계 노트의 화면 모델 그대로.
// 접으면 tip 한 줄(fresh/계승/미진행 3색)만, 펼치면 과거 행이 위로 쌓이며 git graph처럼
// 세로선으로 계보가 이어진다. 세로선은 parent_config가 아니라 백엔드의 research_branches
// 사이드테이블(branched_from_checkpoint_id)에서 얻는다 — 이유는 api/research.ts의
// HistoryEntry 주석 참고.
//
// 08-06 화면 개선 ③④(RoadMap "프론트 개선 백로그" 참고) — "다음으로 갈 수 있는 곳"
// 미리보기(nextOpts 칩)는 이 컴포넌트에서 뺐다. 예전엔 tip 기준 칩을 여기서 읽기 전용으로
// 보여주고, 그 아래 NextOptions.tsx가 같은 선택지를 실제 폼으로 또 보여줘서 중복이었다 —
// 이제 NextOptions.tsx가 "보고 있는 시점 기준" 진짜 선택 가능한 다이어그램 행을 그리므로
// (같은 시각 언어를 재사용), 여기 미리보기는 필요 없어졌다.
export function BranchTimeline({ history, selectedCheckpointId, onSelect }: Props) {
  const [expanded, setExpanded] = useState(false)
  const tip = history[history.length - 1]
  const rows = expanded ? history : [tip]

  const indexById = new Map(history.map((e, i) => [e.checkpoint_id, i]))
  const rowIndexById = new Map(rows.map((e, i) => [e.checkpoint_id, i]))

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
          <svg className="research-branch-svg" width={LANE_WIDTH} height={rows.length * ROW_HEIGHT}>
            {connectors.map((c, i) => {
              if (!c.isBranch) {
                return <line key={i} className="research-branch-line" x1={LANE_X} y1={c.fromY} x2={LANE_X} y2={c.toY} />
              }
              const bulge = Math.min(BULGE_MAX, Math.max(BULGE_MIN, (c.toY - c.fromY) / 5))
              const bx = LANE_X - bulge
              const mid = (c.fromY + c.toY) / 2
              return (
                <path
                  key={i}
                  className="research-branch-line-branch"
                  d={`M ${LANE_X} ${c.fromY} C ${bx} ${mid}, ${bx} ${mid}, ${LANE_X} ${c.toY}`}
                  fill="none"
                />
              )
            })}
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
              style={{ marginLeft: expanded ? LANE_WIDTH : 0 }}
              onClick={() => onSelect(entry.checkpoint_id)}
            >
              <span className="research-branch-row-label">
                {expanded
                  ? `${ts} · ${entry.values.action_label || STAGE_LABELS[entry.stage] || entry.stage}`
                  : '현재 상태'}
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
    </div>
  )
}
