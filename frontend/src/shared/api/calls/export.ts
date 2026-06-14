import { apiFetch, parseFastApiDetail } from '../client';

const FILENAME_REGEX = /filename="?([^";]+)"?/i;

function fallbackFilename(): string {
  const today = new Date().toISOString().slice(0, 10);
  return `summaries-${today}.csv`;
}

function filenameFromHeader(headerValue: string | null): string {
  if (!headerValue) return fallbackFilename();
  const match = FILENAME_REGEX.exec(headerValue);
  return match?.[1]?.trim() || fallbackFilename();
}

/**
 * Trigger a CSV download of the current user's summaries.
 *
 * Uses fetch+Blob (rather than a plain anchor href) so non-2xx responses surface
 * as exceptions the caller can show, instead of the browser cheerfully downloading
 * an error page as `summaries.csv`.
 */
export async function downloadSummariesCsv(): Promise<void> {
  const response = await apiFetch('/summary/export.csv');
  if (!response.ok) {
    const json = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(json, 'Could not export summaries'));
  }
  const blob = await response.blob();
  const filename = filenameFromHeader(response.headers.get('Content-Disposition'));
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  } finally {
    URL.revokeObjectURL(url);
  }
}
