import {
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { getSessionUser, postLogout } from '../../shared/api';
import { createContext, useContext } from "react";

export type User = Record<string, unknown> & {
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

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const userRaw = await getSessionUser();

        if (cancelled) return;

        if (userRaw) {
          const userData: User = {
            id: userRaw.id,
            username: userRaw.username,
            email: userRaw.email,
            avatarUrl: userRaw.avatarUrl ?? undefined,
          };

          setUser(userData);
        } else {
          setUser(null);
        }
      } catch {
        if (!cancelled) {
          setUser(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = (data: { user: User }) => {
    setUser(data.user);
  };

  const logout = async () => {
    try {
      await postLogout();
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
