import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Home } from './pages/Home'
import { Papers } from './pages/Papers'
import { Interests } from './pages/Interests'
import { Equipment } from './pages/Equipment'
import { Notes } from './pages/Notes'
import { Research } from './pages/Research'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/research" element={<Research />} />
        <Route path="/research/:threadId" element={<Research />} />
        <Route path="/papers" element={<Papers />} />
        <Route path="/interests" element={<Interests />} />
        <Route path="/equipment" element={<Equipment />} />
        <Route path="/notes" element={<Notes />} />
      </Route>
    </Routes>
  )
}

export default App
