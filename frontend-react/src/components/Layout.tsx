import { NavLink, Outlet } from 'react-router-dom'
import { ChatPanel } from './ChatPanel'
import './Layout.css'

// 셸 — 왼쪽 네비게이션 + 가운데 라우팅된 메인 콘텐츠 + 오른쪽 항상-떠-있는 챗 패널.
// 화면을 하나씩 이관하는 동안(RoadMap "프론트 스택 전환" 설계 노트) 네비게이션엔
// 실제로 옮겨진 화면만 올린다 — 아직 없는 화면을 눌러도 되는 링크로 남겨두면 거짓
// 안내가 된다.
export function Layout() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-title">🔬 Science Chatbot</div>
        <NavLink to="/" end className="app-nav-link">
          홈
        </NavLink>
        <NavLink to="/research" className="app-nav-link">
          🧬 연구 워크플로우
        </NavLink>
        <NavLink to="/papers" className="app-nav-link">
          📄 논문
        </NavLink>
        <NavLink to="/interests" className="app-nav-link">
          🔬 관심사
        </NavLink>
        <NavLink to="/equipment" className="app-nav-link">
          🧪 실험도구
        </NavLink>
        <NavLink to="/notes" className="app-nav-link">
          📝 지식 노트
        </NavLink>
      </nav>
      <main className="app-main">
        <Outlet />
      </main>
      <ChatPanel />
    </div>
  )
}
