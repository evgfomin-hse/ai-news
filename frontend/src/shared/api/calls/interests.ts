import { apiFetch, parseFastApiDetail } from '../client';

export type InterestMe = {
  interestId: number | null;
  interests: string;
};

export async function getInterestMe(): Promise<InterestMe | null> {
  const response = await apiFetch('/interests/me');
  if (!response.ok) return null;
  
  return (await response.json()) as InterestMe;
}

export async function patchInterestMe(interests: string): Promise<InterestMe> {
  const response = await apiFetch('/interests/me', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interests }),
  });
  if (!response.ok) {
    const json = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(json));
  }

  return (await response.json()) as InterestMe;
}
