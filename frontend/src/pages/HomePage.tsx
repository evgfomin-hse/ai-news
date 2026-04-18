import type { Components } from 'react-markdown';
import type { FC, KeyboardEvent } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiUrl } from '../api';
import { useAuth } from '../AuthContext';
import './homeSummaryArticle.css';

/** Rows per page on home (matches “6 bullets” layout). */
const PAGE_SIZE = 6;

const markdownComponents: Components = {
  a: ({ node: _node, ...props }) => (
    <a {...props} target="_blank" rel="noreferrer noopener" />
  ),
};

type SummaryListItem = { id: string; title: string; body: string };

type UserSummaryResponse = {
  items: SummaryListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  generated_at: string | null;
  notice: string;
};

const SummaryMarkdown: FC<{ text: string }> = ({ text }) => (
  <div className="summary-md">
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {text}
    </ReactMarkdown>
  </div>
);

function formatGeneratedAt(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/** One-line preview for bullet rows (markdown shown in empty-state only). */
function previewPlain(body: string, max = 200): string {
  const flat = body.replace(/\s+/g, ' ').trim();
  if (flat.length <= max) return flat;
  return `${flat.slice(0, max)}…`;
}

function openDetailFromKey(e: KeyboardEvent, it: SummaryListItem, open: (v: SummaryListItem) => void) {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  e.preventDefault();
  open(it);
}

const HomePage: FC = () => {
  const { user } = useAuth();
  const [summaryPayload, setSummaryPayload] = useState<UserSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [genLoading, setGenLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [detailItem, setDetailItem] = useState<SummaryListItem | null>(null);
  const modalCloseRef = useRef<HTMLButtonElement>(null);

  const fetchSummaryPage = useCallback(async (page: number) => {
    setLoading(true);
    setFetchError(null);
    try {
      const qs = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
      });
      const r = await fetch(apiUrl(`/users/me/summary?${qs.toString()}`), {
        credentials: 'include',
      });
      if (!r.ok) {
        const j = (await r.json().catch(() => ({}))) as { detail?: unknown };
        const d = j.detail;
        const msg =
          typeof d === 'string'
            ? d
            : Array.isArray(d)
              ? d.map((x) => String(x)).join(', ')
              : 'Could not load summary';
        throw new Error(msg);
      }
      setSummaryPayload((await r.json()) as UserSummaryResponse);
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : 'Could not load summary');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSummaryPage(1);
  }, [fetchSummaryPage]);

  useEffect(() => {
    if (!detailItem) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    modalCloseRef.current?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') setDetailItem(null);
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [detailItem]);

  const generateMySummary = async () => {
    setGenLoading(true);
    setFetchError(null);
    try {
      const r = await fetch(apiUrl('/users/me/summary/generate'), {
        method: 'POST',
        credentials: 'include',
      });
      if (!r.ok) {
        const j = (await r.json().catch(() => ({}))) as { detail?: unknown };
        const d = j.detail;
        const msg =
          typeof d === 'string'
            ? d
            : Array.isArray(d)
              ? d.map((x) => String(x)).join(', ')
              : 'Could not generate summary';
        throw new Error(msg);
      }
      await fetchSummaryPage(1);
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : 'Could not generate summary');
    } finally {
      setGenLoading(false);
    }
  };

  const today = new Date().toISOString().slice(0, 10);
  const name = String(user?.username ?? 'user');

  return (
    <div className="home">
      <section className="home-head">
        <div>
          <div className="kicker">
            <span className="accent">●</span> brief · {today}
          </div>
          <h2 className="h2">
            good morning, <span className="accent">{name}</span>
            <span className="dim h2-dim"> — summaries from your coursework table.</span>
          </h2>
          <div className="meta-row">
            <span className="pill">
              <span className="accent">{summaryPayload?.total ?? '—'}</span> rows
            </span>
            <span className="pill">
              <span className="accent">{PAGE_SIZE}</span> per page
            </span>
            <span className="pill">
              nightly <span className="accent">00:00</span> UTC
            </span>
          </div>
        </div>
      </section>

      <section className="filter-row">
        <button
          type="button"
          className="btn-primary small"
          disabled={genLoading || loading}
          onClick={() => void generateMySummary()}
        >
          {genLoading ? '…' : '+ generate now'}
        </button>
        <span className="spacer" />
        <Link to="/settings" className="btn-ghost">
          ⚙ tune settings
        </Link>
      </section>

      {fetchError ? (
        <p
          style={{
            marginBottom: 16,
            padding: 12,
            background: 'oklch(0.70 0.16 25 / 0.12)',
            border: '1px solid oklch(0.40 0.10 25)',
            borderRadius: 8,
            fontSize: 13,
            color: 'oklch(0.78 0.14 25)',
          }}
        >
          {fetchError}
        </p>
      ) : null}

      {loading && !summaryPayload ? (
        <p className="dim small" style={{ marginBottom: 12 }}>
          Loading summaries…
        </p>
      ) : null}

      {summaryPayload ? (
        <>
          <p className="dim small" style={{ marginBottom: 12 }}>
            {summaryPayload.total_pages > 0 ? (
              <>
                page {summaryPayload.page} / {summaryPayload.total_pages} · {summaryPayload.total}{' '}
                total
                {summaryPayload.generated_at ? (
                  <>
                    {' '}
                    · latest on page{' '}
                    <time dateTime={summaryPayload.generated_at}>
                      {formatGeneratedAt(summaryPayload.generated_at)}
                    </time>
                  </>
                ) : null}
              </>
            ) : (
              <>0 rows in public.summaries</>
            )}
          </p>
          {summaryPayload.total_pages > 1 ? (
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn-ghost small"
                disabled={loading || summaryPayload.page <= 1}
                onClick={() => void fetchSummaryPage(summaryPayload.page - 1)}
              >
                ← prev
              </button>
              <button
                type="button"
                className="btn-ghost small"
                disabled={loading || summaryPayload.page >= summaryPayload.total_pages}
                onClick={() => void fetchSummaryPage(summaryPayload.page + 1)}
              >
                next →
              </button>
            </div>
          ) : null}

          {summaryPayload.items.length > 0 ? (
            <div className="bullet-list">
              {summaryPayload.items.map((it) => (
                <div
                  key={it.id}
                  className="bullet bullet--clickable"
                  role="button"
                  tabIndex={0}
                  aria-label={`Open summary ${it.id}: ${it.title}`}
                  onClick={() => setDetailItem(it)}
                  onKeyDown={(e) => openDetailFromKey(e, it, setDetailItem)}
                >
                  <span className="bullet-idx">{it.id}</span>
                  <span className="bullet-tag">#summary</span>
                  <div className="bullet-body">
                    <div className="bullet-title">{it.title}</div>
                    <div className="bullet-tldr dim">{previewPlain(it.body)}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="panel" style={{ marginTop: 8 }}>
              <SummaryMarkdown text={summaryPayload.notice} />
            </div>
          )}
        </>
      ) : null}

      {detailItem ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setDetailItem(null)}
        >
          <div
            className="modal-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="summary-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="modal-head">
              <div className="modal-title-block">
                <h2 id="summary-modal-title" className="modal-title">
                  {detailItem.title}
                </h2>
                <div className="modal-id mono">{detailItem.id}</div>
              </div>
              <button
                ref={modalCloseRef}
                type="button"
                className="btn-ghost small"
                aria-label="Close"
                onClick={() => setDetailItem(null)}
              >
                Close
              </button>
            </header>
            <div className="modal-body">
              <SummaryMarkdown text={detailItem.body} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default HomePage;
