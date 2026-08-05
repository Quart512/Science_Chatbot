import { useState } from 'react'
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
//
// 08-05 — 화면 개선 ⑥(RoadMap "프론트 개선 백로그" 참고) 순서 재정렬: 목표는
// "홈 · 챗봇 · 연구 워크플로우"를 한 그룹으로, 그다음 라이브러리, 맨 아래 설정.
// 챗봇 네비 항목은 ⑤(QA 챗을 왼쪽 독립 화면으로)가 아직 안 끝나 존재하지 않는다 —
// ⑥이 ⑤보다 먼저 착수되면서 생긴 순서 충돌(사용자 확인, RoadMap 참고)이라 지금
// 가능한 부분만 미리 반영: 메인 그룹에 홈+연구 워크플로우를 같이 두고(챗봇 자리는
// 비워둠), 설정만 별도 그룹으로 맨 아래로 내린다. ⑤ 착수 시 챗봇 링크를 아래
// 표시한 자리에 끼워 넣으면 된다.
//
// 08-05 — 화면 개선 ⑦(왼쪽 패널 여닫기, 오른쪽 챗 패널의 open 토글과 같은 패턴)·
// ⑨(연구 워크플로우 세션 목록 접기/펼치기) 같이 착수. ⑨는 지금은 ResearchSessionNav
// 하나뿐이라 토글도 하나뿐이지만, ⑤(챗봇 왼쪽 화면)가 생기면 그쪽 세션 목록에도
// 같은 패턴(별도 상태 변수 + 토글 버튼)을 그대로 복사하면 된다.
export function Layout() {
  const [navOpen, setNavOpen] = useState(true)
  const [researchSessionsOpen, setResearchSessionsOpen] = useState(true)

  if (!navOpen) {
    return (
      <div className="app-shell">
        <button className="app-nav-toggle" onClick={() => setNavOpen(true)} aria-label="메뉴 열기">
          ☰
        </button>
        <main className="app-main">
          <Outlet />
        </main>
        <ChatPanel />
      </div>
    )
  }

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-title">
          <span>🔬 AIsaac</span>
          <button className="app-nav-close" onClick={() => setNavOpen(false)} aria-label="메뉴 닫기">
            ✕
          </button>
        </div>

        <div className="app-nav-group">
          <div className="app-nav-group-title">메인</div>
          <NavLink to="/" end className="app-nav-link">
            홈
          </NavLink>
          {/* 챗봇 자리 — ⑤ 착수 시 여기에 왼쪽 독립 챗 화면 링크 삽입 */}
          <div className="app-nav-item-row">
            <NavLink to="/research" className="app-nav-link app-nav-link-grow">
              🧬 연구 워크플로우
            </NavLink>
            <button
              type="button"
              className="app-nav-session-toggle"
              onClick={() => setResearchSessionsOpen((v) => !v)}
              aria-label={researchSessionsOpen ? '세션 목록 접기' : '세션 목록 펼치기'}
            >
              {researchSessionsOpen ? '▾' : '▸'}
            </button>
          </div>
          {researchSessionsOpen && <ResearchSessionNav />}
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

        <div className="app-nav-group">
          <div className="app-nav-group-title">설정</div>
          <NavLink to="/settings" className="app-nav-link">
            ⚙️ 설정
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
