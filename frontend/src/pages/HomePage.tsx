import type { Components } from 'react-markdown';
import type { CSSProperties, FC } from 'react';
import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiUrl } from '../api';
import './homeSummaryArticle.css';

const PAGE_SIZE = 10;

const btn: CSSProperties = {
  display: 'inline-block',
  padding: '10px 18px',
  borderRadius: 8,
  border: '1px solid #ccc',
  background: '#fff',
  cursor: 'pointer',
  textDecoration: 'none',
  color: '#111',
  fontSize: 15,
};

const markdownComponents: Components = {
  a: ({ node: _node, ...props }) => (
    <a {...props} target="_blank" rel="noreferrer noopener" />
  ),
};

type UserSummaryResponse = {
  items: { id: string; title: string; body: string }[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  generated_at: string | null;
  notice: string;
};

const SummaryMarkdown: FC<{ text: string }> = ({ text }) => (
  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
    {text}
  </ReactMarkdown>
);

function formatGeneratedAt(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

const HomePage: FC = () => {
  const [summaryPayload, setSummaryPayload] = useState<UserSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [genLoading, setGenLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

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

  const loadSummaryFromStart = () => {
    setSummaryPayload(null);
    void fetchSummaryPage(1);
  };

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

  return (
    <main style={{ maxWidth: 560, margin: '0 auto', padding: '24px 16px 48px' }}>
      <h1 style={{ marginTop: 0, fontSize: '1.75rem' }}>Home</h1>
      <p style={{ color: '#444', marginBottom: 20 }}>You are signed in.</p>

      <nav style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Link to="/settings" style={btn}>
          Settings
        </Link>
      </nav>

      <section style={{ marginTop: 36, paddingTop: 24, borderTop: '1px solid #eee' }}>
        <h2 style={{ fontSize: '1.15rem', marginBottom: 12 }}>Summary</h2>
        <p style={{ color: '#666', fontSize: 14, marginBottom: 12 }}>
          Paginated markdown from <code>public.summaries</code> ({PAGE_SIZE} per page). A nightly
          task inserts one row per user at <strong>00:00</strong> (timezone from server config,
          default UTC).
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            type="button"
            style={{ ...btn, opacity: loading ? 0.65 : 1, pointerEvents: loading ? 'none' : 'auto' }}
            onClick={() => loadSummaryFromStart()}
          >
            {loading ? 'Loading…' : 'Load summary'}
          </button>
          <button
            type="button"
            style={{
              ...btn,
              opacity: genLoading || loading ? 0.65 : 1,
              pointerEvents: genLoading || loading ? 'none' : 'auto',
            }}
            onClick={() => void generateMySummary()}
          >
            {genLoading ? 'Generating…' : 'Generate now'}
          </button>
        </div>
        {fetchError ? (
          <p
            style={{
              marginTop: 16,
              padding: 12,
              background: '#ffebee',
              color: '#b71c1c',
              borderRadius: 8,
              fontSize: 14,
            }}
          >
            {fetchError}
          </p>
        ) : null}
        {summaryPayload ? (
          <>
            <p
              style={{
                marginTop: 16,
                marginBottom: 0,
                fontSize: 13,
                color: '#666',
              }}
            >
              {summaryPayload.total_pages > 0 ? (
                <>
                  Page {summaryPayload.page} of {summaryPayload.total_pages} ·{' '}
                  {summaryPayload.total} total
                </>
              ) : (
                <>0 summaries</>
              )}
            </p>
            {summaryPayload.generated_at ? (
              <p
                style={{
                  marginTop: 6,
                  marginBottom: 0,
                  fontSize: 13,
                  color: '#666',
                }}
              >
                Latest on this page:{' '}
                <time dateTime={summaryPayload.generated_at}>
                  {formatGeneratedAt(summaryPayload.generated_at)}
                </time>
              </p>
            ) : null}
            {summaryPayload.total_pages > 1 ? (
              <div
                style={{
                  marginTop: 12,
                  display: 'flex',
                  gap: 10,
                  flexWrap: 'wrap',
                  alignItems: 'center',
                }}
              >
                <button
                  type="button"
                  style={{ ...btn, padding: '8px 14px', fontSize: 14 }}
                  disabled={loading || summaryPayload.page <= 1}
                  onClick={() => void fetchSummaryPage(summaryPayload.page - 1)}
                >
                  Previous
                </button>
                <button
                  type="button"
                  style={{ ...btn, padding: '8px 14px', fontSize: 14 }}
                  disabled={loading || summaryPayload.page >= summaryPayload.total_pages}
                  onClick={() => void fetchSummaryPage(summaryPayload.page + 1)}
                >
                  Next
                </button>
              </div>
            ) : null}
            <article
              style={{
                marginTop: 12,
                padding: 16,
                background: '#fafafa',
                borderRadius: 8,
                border: '1px solid #eee',
                lineHeight: 1.55,
                color: '#222',
              }}
            >
              {summaryPayload.items.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {summaryPayload.items.map((it) => (
                    <li key={it.id} style={{ marginBottom: 14 }}>
                      <strong>{it.title}</strong>
                      <div style={{ marginTop: 6 }}>
                        <SummaryMarkdown text={it.body} />
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <SummaryMarkdown text={summaryPayload.notice} />
              )}
            </article>
          </>
        ) : null}
      </section>
    </main>
  );
};

export default HomePage;
