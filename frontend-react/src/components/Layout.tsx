import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { ChatPanel } from './ChatPanel'
import { ChatSessionNav } from './ChatSessionNav'
import { ResearchSessionNav } from './ResearchSessionNav'
import { useScrollbarAutoHide } from '../hooks/useScrollbarAutoHide'
import { LogoMark } from './Logo'
import { ChatIcon, ResearchIcon, PaperIcon, InterestIcon, EquipmentIcon, NoteIcon } from './NavIcons'
import { WelcomeModal } from './WelcomeModal'
import { EmbeddingProgressBanner } from './EmbeddingProgress'
import './Layout.css'

// 첫 실행 안내창과 모델 준비 배너는 어느 화면에 있든 보여야 해서 셸에 붙인다(08-09).
// App.tsx가 아니라 여기인 이유: Layout은 라우터 하위라 필요해지면 useNavigate 같은
// 라우팅 훅을 쓸 수 있고, 네비를 접은 상태(아래 early return)에도 같이 따라간다.
function GlobalOverlays() {
  return (
    <>
      <WelcomeModal />
      <EmbeddingProgressBanner />
    </>
  )
}

// 셸 — 왼쪽 네비게이션 + 가운데 라우팅된 메인 콘텐츠 + 오른쪽 항상-떠-있는 챗 패널.
// 08-04 사용자 지적으로 두 가지 복원/변경: ① Streamlit app.py에 있던 "메인/연구/
// 라이브러리" 그룹 헤더를 React 이관 때 평평한 목록으로 단순화해버렸던 걸 되살림.
// ② 연구 세션 목록을 Research.tsx 안의 별도 사이드바 컬럼이 아니라 "연구 워크플로우"
// 항목 바로 아래 중첩된 목록으로(`ResearchSessionNav`) — 화면을 하나씩 이관하는 동안
// 실제로 옮겨진 화면만 올린다는 원칙은 유지(아직 없는 화면을 링크로 남기지 않음).
//
// 08-05 — 화면 개선 ⑥(RoadMap "프론트 개선 백로그" 참고) 순서 재정렬: 목표는
// "홈 · 챗봇 · 연구 워크플로우"를 한 그룹으로, 그다음 라이브러리, 맨 아래 설정.
//
// 08-05 — 화면 개선 ⑦(왼쪽 패널 여닫기, 오른쪽 챗 패널의 open 토글과 같은 패턴)·
// ⑨(세션 목록 접기/펼치기) 같이 착수 — 연구 워크플로우에 먼저 붙인 패턴(별도 상태
// 변수 + 토글 버튼)을 08-06(⑤)에 챗봇 세션 목록에도 그대로 복사했다.
export function Layout() {
  const [navOpen, setNavOpen] = useState(true)
  const [chatSessionsOpen, setChatSessionsOpen] = useState(true)
  const [researchSessionsOpen, setResearchSessionsOpen] = useState(true)
  useScrollbarAutoHide()

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
        <GlobalOverlays />
      </div>
    )
  }

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-title">
          <span className="app-nav-brand">
            <LogoMark size={20} />
            AIsaac
          </span>
          <button className="app-nav-close" onClick={() => setNavOpen(false)} aria-label="메뉴 닫기">
            ✕
          </button>
        </div>
        <div className="app-nav-spectrum" aria-hidden="true" />

        <div className="app-nav-group">
          <div className="app-nav-group-title">메인</div>
          <NavLink to="/" end className="app-nav-link">
            홈
          </NavLink>
          <div className="app-nav-item-row">
            <NavLink to="/chat" className="app-nav-link app-nav-link-grow">
              <ChatIcon /> 챗봇
            </NavLink>
            <NavLink to="/chat/new" className="app-nav-new-session" title="새 대화 시작" aria-label="새 대화 시작">
              +
            </NavLink>
            <button
              type="button"
              className="app-nav-session-toggle"
              onClick={() => setChatSessionsOpen((v) => !v)}
              aria-label={chatSessionsOpen ? '세션 목록 접기' : '세션 목록 펼치기'}
            >
              {chatSessionsOpen ? '▾' : '▸'}
            </button>
          </div>
          {chatSessionsOpen && <ChatSessionNav />}
          <div className="app-nav-item-row">
            <NavLink to="/research" className="app-nav-link app-nav-link-grow">
              <ResearchIcon /> 연구 워크플로우
            </NavLink>
            <NavLink to="/research/new" className="app-nav-new-session" title="새 연구 시작" aria-label="새 연구 시작">
              +
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
            <PaperIcon /> 논문
          </NavLink>
          <NavLink to="/interests" className="app-nav-link">
            <InterestIcon /> 관심사
          </NavLink>
          <NavLink to="/equipment" className="app-nav-link">
            <EquipmentIcon /> 실험도구
          </NavLink>
          <NavLink to="/notes" className="app-nav-link">
            <NoteIcon /> 지식 노트
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
      <GlobalOverlays />
    </div>
  )
}
