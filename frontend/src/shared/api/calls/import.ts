import { apiFetch, parseFastApiDetail } from '../client';

export type ImportSummariesResult = {
  summaries_imported: number;
  scores_imported: number;
};

type ImportErrorDetail = {
  error?: string;
  problems?: unknown;
};

/** Pull the per-row problems out of a 400 invalid_csv response, if present. */
function messageFromImportError(json: { detail?: unknown }): string {
  const detail = json.detail as ImportErrorDetail | string | undefined;
  if (detail && typeof detail === 'object' && Array.isArray(detail.problems)) {
    const problems = detail.problems.map(String);
    if (problems.length > 0) return problems.join('\n');
  }
  return parseFastApiDetail(json as { detail?: unknown }, 'Could not import summaries');
}

/**
 * Upload a CSV (in the export format) to create new summaries — and their scores —
 * for the current user. The server ignores the file's summary_id column, so every
 * row becomes a brand-new summary. Import is all-or-nothing: a single bad row
 * rejects the whole file.
 */
export async function uploadSummariesCsv(file: File): Promise<ImportSummariesResult> {
  const form = new FormData();
  form.append('file', file);

  // No explicit Content-Type: the browser sets multipart/form-data with its boundary.
  const response = await apiFetch('/summary/import.csv', { method: 'POST', body: form });

  const json = (await response.json().catch(() => ({}))) as
    | ImportSummariesResult
    | { detail?: unknown };

  if (!response.ok) {
    throw new Error(messageFromImportError(json as { detail?: unknown }));
  }
  return json as ImportSummariesResult;
}
