import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { LabLoginPage } from './pages/LabLogin'
import { MonitorPage } from './pages/Monitor'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LabLoginPage />} />
        <Route path="/lab" element={<Navigate to="/" replace />} />
        <Route path="/monitor" element={<MonitorPage focus="overview" />} />
        <Route path="/alerts" element={<MonitorPage focus="alerts" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
