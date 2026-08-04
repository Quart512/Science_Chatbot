import { NavLink, Outlet } from 'react-router-dom'
import { ChatPanel } from './ChatPanel'
import { ResearchSessionNav } from './ResearchSessionNav'
import './Layout.css'

// 셸 — 왼쪽 네비게이션 + 가운데 라우팅된 메인 콘텐츠 + 오른쪽 항상-떠-있는 챗 패널.
// 08-04 사용자 지적으로 두 가지 복원/변경: ① Streamlit app.py에 있던 "메인/연구/
// 라이브러리" 그룹 헤더를 React 이관 때 평평한 목록으로 단순화해버렸던 걸 되살림.
// ② 연구 세션 목록을 Research.tsx 안의 별도 사이드바 컬럼이 아니라 "연구 워크플로우"
// 항목 바로 아래 중첩된 목록으로(`ResearchSessionNav`) — 화면을 하나씩 이관하는 동안
// 실제로 옮겨진 화면만 올린다는 원칙은 유지(아직 없는 화면을 링크로 남기지 않음).
export function Layout() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-title">🔬 AIsaac</div>

        <div className="app-nav-group">
          <div className="app-nav-group-title">메인</div>
          <NavLink to="/" end className="app-nav-link">
            홈
          </NavLink>
        </div>

        <div className="app-nav-group">
          <div className="app-nav-group-title">연구</div>
          <NavLink to="/research" className="app-nav-link">
            🧬 연구 워크플로우
          </NavLink>
          <ResearchSessionNav />
        </div>

        <div className="app-nav-group">
          <div className="app-nav-group-title">라이브러리</div>
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
        </div>
      </nav>
      <main className="app-main">
        <Outlet />
      </main>
      <ChatPanel />
    </div>
  )
}
