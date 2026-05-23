import { apiFetch, parseFastApiDetail } from '../client';

export type ScoreView = {
  id: number;
  summary_id: number;
  value: boolean | null;
  description: string | null;
};

export async function putScore(
  summaryId: number,
  value: boolean,
  description: string | null,
): Promise<ScoreView> {
  const response = await apiFetch('/score', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      summary_id: summaryId,
      value,
      description,
    }),
  });
  if (!response.ok) {
    const json = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(json, 'Could not save your feedback'));
  }
  return (await response.json()) as ScoreView;
}

/** Returns the existing score, or null if no vote yet. Throws on real errors. */
export async function getScore(summaryId: number): Promise<ScoreView | null> {
  const response = await apiFetch(`/score/${summaryId}`);
  if (response.status === 404) {
    // Summary doesn't exist or isn't owned by this user — treat as "no score" for UI purposes.
    return null;
  }
  if (!response.ok) {
    const json = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(json, 'Could not load your feedback'));
  }
  const body = (await response.json()) as ScoreView | null;
  return body;
}
