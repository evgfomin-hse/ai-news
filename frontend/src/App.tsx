import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './features/Auth/AuthProvider';
import Home from './pages/Home';
import Login from './pages/Login';
import Settings from './pages/Settings';

export default function App() {
  const { user } = useAuth();

  if (!user) {
    return (
      <main>
        <Login />
      </main>
    );
  }

  return (
    <main>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </main>
  );
}
