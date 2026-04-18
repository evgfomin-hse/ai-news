/** API origin: use `/api` in dev (Vite proxy → backend) so session cookies are same-site. */
const raw = import.meta.env.VITE_API_URL as string | undefined;

export const API_BASE =
  raw != null && String(raw).trim() !== '' ? String(raw).replace(/\/$/, '') : '/api';

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${p}`;
}
