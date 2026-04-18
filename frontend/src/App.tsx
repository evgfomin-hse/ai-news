import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './AuthContext';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  const { user } = useAuth();

  if (!user) {
    return (
      <main className="main">
        <LoginPage />
      </main>
    );
  }

  return (
    <main className="main">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </main>
  );
}
