import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { apiUrl } from './api';

type User = Record<string, unknown> & {
  id?: string;
  username?: string;
  email?: string;
  avatarUrl?: string;
};

type AuthContextType = {
  user: User | null;
  login: (data: { user: User }) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function readStoredUser(): User | null {
  try {
    const storedUser = localStorage.getItem('user');
    return storedUser ? (JSON.parse(storedUser) as User) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readStoredUser);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await fetch(apiUrl('/users/me'), { credentials: 'include' });
        if (cancelled) return;
        if (r.ok) {
          const u = (await r.json()) as {
            id: string;
            username: string;
            email: string;
            avatarUrl?: string | null;
          };
          const next: User = {
            id: u.id,
            username: u.username,
            email: u.email,
            avatarUrl: u.avatarUrl ?? undefined,
          };
          setUser(next);
          localStorage.setItem('user', JSON.stringify(next));
        } else {
          setUser(null);
          localStorage.removeItem('user');
        }
      } catch {
        if (!cancelled) {
          setUser(null);
          localStorage.removeItem('user');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = (data: { user: User }) => {
    localStorage.setItem('user', JSON.stringify(data.user));
    setUser(data.user);
  };

  const logout = async () => {
    try {
      await fetch(apiUrl('/auth/logout'), {
        method: 'POST',
        credentials: 'include',
      });
    } finally {
      localStorage.removeItem('user');
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
