import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Home } from './pages/Home'
import { Chat } from './pages/Chat'
import { Papers } from './pages/Papers'
import { Interests } from './pages/Interests'
import { Equipment } from './pages/Equipment'
import { Notes } from './pages/Notes'
import { Research } from './pages/Research'
import { Settings } from './pages/Settings'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/chat/:threadId" element={<Chat />} />
        <Route path="/research" element={<Research />} />
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
