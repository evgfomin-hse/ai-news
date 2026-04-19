import type { Components } from 'react-markdown';
import type { FC, KeyboardEvent } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  getUserSummaryPage,
  postGenerateUserSummary,
  type SummaryListItem,
  type UserSummaryResponse,
} from '../../shared/api';
import { useAuth } from '../../features/Auth/AuthProvider';
import styles from './style.module.css';

/** Rows per page on home (matches “6 bullets” layout). */
const PAGE_SIZE = 6;

const markdownComponents: Components = {
  a: ({ node: _node, ...props }) => (
    <a {...props} target="_blank" rel="noreferrer noopener" />
  ),
};

const SummaryMarkdown: FC<{ text: string }> = ({ text }) => (
  <div className={styles.summaryMd}>
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {text}
    </ReactMarkdown>
  </div>
);

function formatGeneratedAt(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function formatListDate(iso: string): string {
  const d = new Date(`${iso}T12:00:00Z`);
  return d.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
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

const Home: FC = () => {
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
      const payload = await getUserSummaryPage(page, PAGE_SIZE);
      setSummaryPayload(payload);
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
      await postGenerateUserSummary();
      await fetchSummaryPage(1);
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : 'Could not generate summary');
    } finally {
      setGenLoading(false);
    }
  };

  const todayIso = new Date().toISOString().slice(0, 10);
  const listDateLabel = formatListDate(todayIso);
  const name = String(user?.username ?? 'user');
  const total = summaryPayload?.total ?? 0;
  const page = summaryPayload?.page ?? 1;
  const totalPages = summaryPayload?.total_pages ?? 0;
  const readyLabel =
    summaryPayload && totalPages > 0
      ? `${summaryPayload.items.length} / ${PAGE_SIZE} on this page`
      : loading && !summaryPayload
        ? '…'
        : '0 rows';

  return (
    <div className={styles.page}>
      <div className={styles.screen}>
        <div className={styles.screenHead}>
          <div className={styles.dots} aria-hidden>
            <span className={styles.dotWin} />
            <span className={styles.dotWin} />
            <span className={styles.dotWin} />
          </div>
          <span className={styles.url}>ainews.app</span>
          <span className={styles.badge}>HOME</span>
        </div>

        <div className={styles.masthead}>
          <div className={styles.mastCell}>
            <h1 className={styles.mastTitle}>
              Good morning, <b>{name}.</b>
            </h1>
          </div>
          <div className={styles.mastCell}>
            <div className={styles.kvLabel}>
              TODAY<u>{total} stories</u>
            </div>
          </div>
          <div className={styles.mastCell}>
            <div className={styles.kvLabel}>
              ON PAGE<u>{summaryPayload?.items.length ?? (loading ? '…' : 0)}</u>
            </div>
          </div>
          <div className={styles.mastCell}>
            <div className={styles.kvLabel}>
              NEXT DROP<u>00:00 UTC</u>
            </div>
          </div>
        </div>

        {fetchError ? <p className={styles.error}>{fetchError}</p> : null}

        {loading && !summaryPayload ? (
          <p className={`${styles.metaLine} ${styles.emptyPanel}`}>Loading summaries…</p>
        ) : null}

        {summaryPayload ? (
          <>
            <div className={styles.feed}>
              <div className={styles.grp}>
                <div className={styles.grpHead}>
                  <div className={styles.grpA}>
                    01 — <em>TODAY</em>
                  </div>
                  <div className={styles.grpB}>{listDateLabel}</div>
                  <div className={styles.grpC}>{readyLabel}</div>
                </div>

                {summaryPayload.items.length > 0 ? (
                  summaryPayload.items.map((it, idx) => (
                    <div
                      key={it.id}
                      className={styles.rowItem}
                      role="button"
                      tabIndex={0}
                      aria-label={`Open summary ${it.id}: ${it.title}`}
                      onClick={() => setDetailItem(it)}
                      onKeyDown={(e) => openDetailFromKey(e, it, setDetailItem)}
                    >
                      <div className={styles.rowN}>
                        #<b>{String(idx + 1 + (page - 1) * PAGE_SIZE).padStart(2, '0')}</b>
                      </div>
                      <div>
                        <h2 className={styles.rowTitle}>{it.title}</h2>
                        <p className={styles.rowBody}>{previewPlain(it.body)}</p>
                      </div>
                      <div className={styles.rowMeta}>
                        <span>SUMMARY</span>
                        ROW {it.id}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className={styles.emptyPanel}>
                    <SummaryMarkdown text={summaryPayload.notice} />
                  </div>
                )}
              </div>
            </div>

            <div className={styles.homeFoot}>
              <div className={styles.footCell}>
                <div className={styles.footLab}>SUMMARY · PAGINATION</div>
                <div className={styles.footVal}>
                  {totalPages > 0 ? (
                    <>
                      Page {page} of {totalPages} · {total} total
                      {summaryPayload.generated_at ? (
                        <>
                          {' '}
                          · latest{' '}
                          <time dateTime={summaryPayload.generated_at}>
                            {formatGeneratedAt(summaryPayload.generated_at)}
                          </time>
                        </>
                      ) : null}
                    </>
                  ) : (
                    <>0 rows in public.summaries</>
                  )}
                </div>
              </div>
              <div className={styles.footCell}>
                <div className={styles.footLab}>PAGING</div>
                <div className={`${styles.actions} ${styles.pager}`}>
                  <button
                    type="button"
                    className={styles.swBtn}
                    disabled={loading || !summaryPayload || summaryPayload.page <= 1}
                    onClick={() => void fetchSummaryPage(summaryPayload.page - 1)}
                  >
                    ← PREV
                  </button>
                  <button
                    type="button"
                    className={styles.swBtn}
                    disabled={loading || !summaryPayload || summaryPayload.page >= summaryPayload.total_pages}
                    onClick={() => void fetchSummaryPage(summaryPayload.page + 1)}
                  >
                    NEXT →
                  </button>
                </div>
              </div>
              <div className={styles.footCell}>
                <div className={styles.footLab}>ACTION</div>
                <div className={styles.actions}>
                  <button
                    type="button"
                    className={`${styles.swBtn} ${styles.swBtnPrime}`}
                    disabled={genLoading || loading}
                    onClick={() => void generateMySummary()}
                  >
                    {genLoading ? '…' : 'GENERATE NOW →'}
                  </button>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>

      {detailItem ? (
        <div
          className={styles.modalBackdrop}
          role="presentation"
          onClick={() => setDetailItem(null)}
        >
          <div
            className={styles.modalSheet}
            role="dialog"
            aria-modal="true"
            aria-labelledby="summary-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <header className={styles.modalHead}>
              <div className={styles.modalTitleBlock}>
                <h2 id="summary-modal-title" className={styles.modalTitle}>
                  {detailItem.title}
                </h2>
                <div className={styles.modalId}>{detailItem.id}</div>
              </div>
              <button
                ref={modalCloseRef}
                type="button"
                className={styles.btnGhost}
                aria-label="Close"
                onClick={() => setDetailItem(null)}
              >
                Close
              </button>
            </header>
            <div className={styles.modalBody}>
              <SummaryMarkdown text={detailItem.body} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default Home;
