import { createContext, useContext, useState, type ReactNode } from 'react';
import Header from './components/Header';

type User = Record<string, unknown> & {
  id?: string;
  username?: string;
  avatarUrl?: string;
};

type AuthContextType = {
  user: User | null;
  login: (data: { token: string; user: User }) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const storedUser = localStorage.getItem('user');
      return storedUser ? (JSON.parse(storedUser) as User) : null;
    } catch {
      return null;
    }
  });

  const login = (data: { token: string; user: User }) => {
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data.user));
    setUser(data.user);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      <Header />
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};