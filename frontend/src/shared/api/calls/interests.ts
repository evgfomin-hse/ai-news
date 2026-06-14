import { apiFetch, parseFastApiDetail } from '../client';

export type InterestView = {
  interestId: number | null;
  interests: string;
};

export async function getInterest(): Promise<InterestView | null> {
  const response = await apiFetch('/interests');
  if (!response.ok) return null;

  return (await response.json()) as InterestView;
}

export async function patchInterest(interests: string): Promise<InterestView> {
  const response = await apiFetch('/interests', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interests }),
  });
  if (!response.ok) {
    const json = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(json));
  }

  return (await response.json()) as InterestView;
}
