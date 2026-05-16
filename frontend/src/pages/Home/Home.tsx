import type { Components } from 'react-markdown';
import type { FC, KeyboardEvent } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  getUserSummaryPage,
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

const MS_DAY = 86_400_000;

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/** Milliseconds from `from` until the next 00:00:00.000 UTC. */
function msUntilNextUtcMidnight(from: Date): number {
  const y = from.getUTCFullYear();
  const mo = from.getUTCMonth();
  const da = from.getUTCDate();
  const startUtcDay = Date.UTC(y, mo, da, 0, 0, 0, 0);
  const next =
    from.getTime() < startUtcDay ? startUtcDay : Date.UTC(y, mo, da + 1, 0, 0, 0, 0);
  return next - from.getTime();
}

const DropCountdown: FC = () => {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const msLeft = msUntilNextUtcMidnight(now);
  const totalSec = Math.max(0, Math.floor(msLeft / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;

  const y = now.getUTCFullYear();
  const mo = now.getUTCMonth();
  const da = now.getUTCDate();
  const startUtcDay = Date.UTC(y, mo, da, 0, 0, 0, 0);
  const dayProgress = Math.min(1, Math.max(0, (now.getTime() - startUtcDay) / MS_DAY));

  const nextIso = new Date(now.getTime() + msLeft).toISOString().slice(0, 10);

  const ariaLabel = `${h} hours, ${m} minutes, ${s} seconds until the next drop at midnight UTC`;

  return (
    <div
      className={styles.dropCountdown}
      role="timer"
      aria-live="polite"
      aria-label={ariaLabel}
    >
      <div className={styles.dropCountRow}>
        <div className={styles.dropSeg}>{pad2(h)}</div>
        <span className={styles.dropSep} aria-hidden>
          :
        </span>
        <div className={styles.dropSeg}>{pad2(m)}</div>
        <span className={styles.dropSep} aria-hidden>
          :
        </span>
        <div className={styles.dropSeg}>{pad2(s)}</div>
      </div>
      <div className={styles.dropProgress} aria-hidden>
        <div className={styles.dropProgressFill} style={{ width: `${dayProgress * 100}%` }} />
      </div>
      <div className={styles.dropSub}>Until 00:00 UTC · {nextIso}</div>
    </div>
  );
};

type SummaryFeedback = {
  liked: boolean | null;
  description: string;
};

const Home: FC = () => {
  const { user } = useAuth();
  const [summaryPayload, setSummaryPayload] = useState<UserSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [detailItem, setDetailItem] = useState<SummaryListItem | null>(null);
  const [feedbackBySummaryId, setFeedbackBySummaryId] = useState<Record<string, SummaryFeedback>>({});
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

  const exportToCsv = () => {
    // Placeholder: CSV export will be implemented later.
  };

  const setDetailVote = (liked: boolean) => {
    if (!detailItem) return;
    setFeedbackBySummaryId((prev) => {
      const current = prev[detailItem.id] ?? { liked: null, description: '' };
      return {
        ...prev,
        [detailItem.id]: {
          ...current,
          liked,
        },
      };
    });
  };

  const setDetailDescription = (description: string) => {
    if (!detailItem) return;
    setFeedbackBySummaryId((prev) => {
      const current = prev[detailItem.id] ?? { liked: null, description: '' };
      return {
        ...prev,
        [detailItem.id]: {
          ...current,
          description,
        },
      };
    });
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
    <>
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
            NEXT DROP
            <DropCountdown />
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
                  <>0 summaries generated yet</>
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
                  disabled={loading}
                  onClick={exportToCsv}
                >
                  EXPORT TO CSV →
                </button>
              </div>
            </div>
          </div>
        </>
      ) : null}

      {detailItem ? (
        (() => {
          const feedback = feedbackBySummaryId[detailItem.id] ?? { liked: null, description: '' };
          return (
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
              <section className={styles.feedbackPanel} aria-label="Summary feedback">
                <div className={styles.feedbackTitle}>Was this summary useful?</div>
                <div className={styles.feedbackActions}>
                  <button
                    type="button"
                    className={`${styles.swBtn} ${feedback.liked === true ? styles.feedbackBtnActive : ''}`}
                    onClick={() => setDetailVote(true)}
                    aria-pressed={feedback.liked === true}
                  >
                    Like
                  </button>
                  <button
                    type="button"
                    className={`${styles.swBtn} ${feedback.liked === false ? styles.feedbackBtnActive : ''}`}
                    onClick={() => setDetailVote(false)}
                    aria-pressed={feedback.liked === false}
                  >
                    Dislike
                  </button>
                </div>
                <label htmlFor="summary-feedback-description" className={styles.feedbackLabel}>
                  What did you like or dislike?
                </label>
                <textarea
                  id="summary-feedback-description"
                  className={styles.feedbackInput}
                  placeholder="Write a short comment..."
                  value={feedback.description}
                  onChange={(e) => setDetailDescription(e.target.value)}
                />
              </section>
            </div>
          </div>
        </div>
          );
        })()
      ) : null}
    </>
  );
};

export default Home;
