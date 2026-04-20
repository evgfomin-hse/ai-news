import { apiFetch, parseFastApiDetail } from '../client';

export type SummaryListItem = { id: string; title: string; body: string };

export type UserSummaryResponse = {
  items: SummaryListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  generated_at: string | null;
  notice: string;
};

export async function getUserSummaryPage(
  page: number,
  pageSize: number,
): Promise<UserSummaryResponse> {
  const qs = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const response = await apiFetch(`/users/summary?${qs.toString()}`);
 
  if (!response.ok) {
    const json = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(json, 'Could not load summary'));
  }
  
  return (await response.json()) as UserSummaryResponse;
}

export async function postGenerateUserSummary(): Promise<void> {
  const response = await apiFetch('/users/summary/generate', { method: 'POST' });
 
  if (!response.ok) {
    const j = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(j, 'Could not generate summary'));
  }
}
