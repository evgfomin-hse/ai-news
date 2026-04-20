import { apiFetch } from '../client';

export type SessionUser = {
  id?: string;
  username?: string;
  email?: string;
  avatarUrl?: string | null;
};

export async function getSessionUser(): Promise<SessionUser | null> {
  const response = await apiFetch('/user');
  
  if (!response.ok) return null;

  return (await response.json()) as SessionUser;
}

export async function postLogout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' });
}

export async function postGoogleLogin(
  idToken: string,
): Promise<{ user: SessionUser }> {
  const response = await apiFetch('/auth/google-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: idToken }),
  });

  if (!response.ok) throw new Error('Login failed');
  
  return (await response.json()) as { user: SessionUser };
}
