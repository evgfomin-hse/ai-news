export const API_BASE = import.meta.env.VITE_API_URL || '/api'

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${p}`;
}
