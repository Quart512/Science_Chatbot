import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Home } from './pages/Home'
import { Chat } from './pages/Chat'
import { ChatSessionList } from './pages/ChatSessionList'
import { Papers } from './pages/Papers'
import { Interests } from './pages/Interests'
import { Equipment } from './pages/Equipment'
import { Notes } from './pages/Notes'
import { Research } from './pages/Research'
import { ResearchSessionList } from './pages/ResearchSessionList'
import { Settings } from './pages/Settings'

// 08-06 — 왼쪽 네비 라벨/"+" 동작 분리(RoadMap "왼쪽 네비 — 챗봇·연구 워크플로우
// '+'/라벨 클릭 동작 재설계" 참고). /chat·/research(파라미터 없음)는 이제 "새 세션"이
// 아니라 세션 목록 카드 화면 — 새로 시작하는 진입점은 /chat/new·/research/new로
// 옮기고, Chat.tsx·Research.tsx는 원래 "threadId 없으면 새 세션 폼" 로직을 그대로
// 재사용한다(컴포넌트 내부는 안 바뀜 — 그 분기에 도달하는 경로만 바뀜).
function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/chat" element={<ChatSessionList />} />
        <Route path="/chat/new" element={<Chat />} />
        <Route path="/chat/:threadId" element={<Chat />} />
        <Route path="/research" element={<ResearchSessionList />} />
        <Route path="/research/new" element={<Research />} />
        <Route path="/research/:threadId" element={<Research />} />
        <Route path="/papers" element={<Papers />} />
        <Route path="/interests" element={<Interests />} />
        <Route path="/equipment" element={<Equipment />} />
        <Route path="/notes" element={<Notes />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
