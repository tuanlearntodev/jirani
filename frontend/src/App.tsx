import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Library from './pages/Library'
import ReadBook from './pages/Book'
import Video from './pages/Video'
import Setup from './pages/Setup'

function App() {
    return (
        <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/library" element={<Library />} />
            <Route path="/read/:uid" element={<ReadBook />} />
            <Route path="/video" element={<Video />} />
            <Route path="/setup" element={<Setup />} />
        </Routes>
    )
}

export default App