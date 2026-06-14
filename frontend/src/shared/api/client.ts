import { apiUrl } from './api';

export type ApiErrorBody = { detail?: unknown };

export function parseFastApiDetail(
  body: ApiErrorBody,
  fallback = 'Request failed',
): string {
  const detail = body.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((x) =>
        typeof x === 'object' && x && 'msg' in x
          ? String((x as { msg: string }).msg)
          : String(x),
      )
      .join(', ');
  }
  return fallback;
}

type ApiInit = Omit<RequestInit, 'credentials'> & {
  credentials?: RequestCredentials;
};

export function apiFetch(path: string, init?: ApiInit): Promise<Response> {
  return fetch(apiUrl(path), {
    credentials: 'include',
    ...init,
  });
}
