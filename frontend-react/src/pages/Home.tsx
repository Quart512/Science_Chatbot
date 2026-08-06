import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listInterests } from '../api/interests'
import { listPapers } from '../api/papers'
import { listEquipment } from '../api/equipment'
import { listNotes } from '../api/notes'
import { listChatSessions, type ChatSession } from '../api/chat'
import { listResearchSessions, type ResearchSession } from '../api/research'
import { STAGE_LABELS } from './research/constants'
import { Logo } from '../components/Logo'
import './Home.css'

const STAT_TILES = [
  { key: 'interests', label: '관심사', icon: '🔬', to: '/interests' },
  { key: 'papers', label: '보유 논문', icon: '📄', to: '/papers' },
  { key: 'equipment', label: '실험도구', icon: '🧪', to: '/equipment' },
  { key: 'notes', label: '지식 노트', icon: '📝', to: '/notes' },
] as const

type ActivityItem =
  | { kind: 'chat'; session: ChatSession }
  | { kind: 'research'; session: ResearchSession }

// 08-06 — Phase 0 이관 때 만든 자리표시(연결 확인용 디버그 문구)를 실제 대시보드로
// 교체. 새 데이터를 만들지 않고 라이브러리 4곳 + 세션 2곳이 이미 갖고 있는 목록을
// 모아 보여주기만 한다 — 통계는 각 리스트의 length, "최근 활동"은 두 세션 목록을
// updated_at 기준으로 합쳐 정렬한 것뿐이라 새 백엔드 작업이 필요 없다.
export function Home() {
  const interestsQuery = useQuery({ queryKey: ['interests'], queryFn: listInterests })
  const papersQuery = useQuery({ queryKey: ['papers', 'owned', '', ''], queryFn: () => listPapers('owned') })
  const equipmentQuery = useQuery({ queryKey: ['equipment'], queryFn: listEquipment })
  const notesQuery = useQuery({ queryKey: ['notes', ''], queryFn: () => listNotes() })
  const chatSessionsQuery = useQuery({ queryKey: ['chat-sessions'], queryFn: listChatSessions })
  const researchSessionsQuery = useQuery({ queryKey: ['research-sessions'], queryFn: listResearchSessions })

  const counts: Record<(typeof STAT_TILES)[number]['key'], number | null> = {
    interests: interestsQuery.data?.interests.length ?? null,
    papers: papersQuery.data?.papers.length ?? null,
    equipment: equipmentQuery.data?.equipment.length ?? null,
    notes: notesQuery.data?.notes.length ?? null,
  }

  const activity: ActivityItem[] = [
    ...(chatSessionsQuery.data?.sessions.map((session) => ({ kind: 'chat', session }) as const) ?? []),
    ...(researchSessionsQuery.data?.sessions.map((session) => ({ kind: 'research', session }) as const) ?? []),
  ]
    .sort((a, b) => b.session.updated_at.localeCompare(a.session.updated_at))
    .slice(0, 6)

  return (
    <div className="home-page">
      <div className="home-header">
        <Logo size={40} showWordmark={false} />
        <div>
          <h1>AIsaac</h1>
          <p className="home-tagline">물리 연구를 돕는 개인용 AI 어시스턴트</p>
        </div>
      </div>

      <div className="home-stats">
        {STAT_TILES.map((tile) => (
          <Link key={tile.key} to={tile.to} className="home-stat-tile">
            <span className="home-stat-icon" aria-hidden="true">
              {tile.icon}
            </span>
            <span className="home-stat-value">{counts[tile.key] ?? '—'}</span>
            <span className="home-stat-label">{tile.label}</span>
          </Link>
        ))}
      </div>

      <div className="home-quick-actions">
        <Link to="/chat/new" className="home-quick-action">
          💬 새 대화 시작
        </Link>
        <Link to="/research/new" className="home-quick-action">
          🧬 새 연구 시작
        </Link>
      </div>

      <div className="home-activity">
        <h2>최근 활동</h2>
        {chatSessionsQuery.isLoading || researchSessionsQuery.isLoading ? (
          <p className="home-activity-empty">불러오는 중...</p>
        ) : activity.length === 0 ? (
          <p className="home-activity-empty">아직 활동이 없습니다 — 위에서 대화나 연구를 시작해보세요.</p>
        ) : (
          <ul className="home-activity-list">
            {activity.map((item) =>
              item.kind === 'chat' ? (
                <li key={`chat-${item.session.thread_id}`}>
                  <Link to={`/chat/${item.session.thread_id}`} className="home-activity-row">
                    <span className="home-activity-kind">💬</span>
                    <span className="home-activity-title">{item.session.title || '(제목 없음)'}</span>
                    <span className="home-activity-date">{item.session.updated_at.slice(0, 10)}</span>
                  </Link>
                </li>
              ) : (
                <li key={`research-${item.session.thread_id}`}>
                  <Link to={`/research/${item.session.thread_id}`} className="home-activity-row">
                    <span className="home-activity-kind">🧬</span>
                    <span className="home-activity-title">{item.session.title || item.session.topic}</span>
                    <span className="home-activity-stage">{STAGE_LABELS[item.session.stage] ?? item.session.stage}</span>
                    <span className="home-activity-date">{item.session.updated_at.slice(0, 10)}</span>
                  </Link>
                </li>
              ),
            )}
          </ul>
        )}
      </div>
    </div>
  )
}
