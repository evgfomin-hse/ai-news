import type { Components } from "react-markdown";
import type { FC, KeyboardEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  deleteUserSummary,
  downloadSummariesCsv,
  getAllTimeStats,
  getScore,
  getTodayStats,
  getUserSummaryPage,
  putScore,
  uploadSummariesCsv,
  type SummaryListItem,
  type UserSummaryResponse,
} from "../../shared/api";
import { useAuth } from "../../features/Auth";
import styles from "./style.module.css";

const PAGE_SIZE = 6;

const markdownComponents: Components = {
  a: ({ ...props }) => <a {...props} rel="noreferrer noopener" />,
};

const SummaryMarkdown: FC<{ text: string }> = ({ text }) => (
  <div className={styles.summaryMd}>
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {text}
    </ReactMarkdown>
  </div>
);

function formatGeneratedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

function formatListDate(iso: string): string {
  const date = new Date(`${iso}T12:00:00Z`);
  return date.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function previewPlain(body: string, max = 200): string {
  const flat = body.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  return `${flat.slice(0, max)}…`;
}

function openDetailFromKey(
  e: KeyboardEvent,
  it: SummaryListItem,
  open: (v: SummaryListItem) => void,
) {
  if (e.key !== "Enter" && e.key !== " ") return;
  e.preventDefault();
  open(it);
}

const MS_DAY = 86_400_000;

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function msUntilNextUtcMidnight(from: Date): number {
  const year = from.getUTCFullYear();
  const month = from.getUTCMonth();
  const day = from.getUTCDate();
  const startUtcDay = Date.UTC(year, month, day, 0, 0, 0, 0);
  const next =
    from.getTime() < startUtcDay
      ? startUtcDay
      : Date.UTC(year, month, day + 1, 0, 0, 0, 0);
  return next - from.getTime();
}

const DropCountdown: FC = () => {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const msLeft = msUntilNextUtcMidnight(now);
  const totalSeconds = Math.max(0, Math.floor(msLeft / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const yer = now.getUTCFullYear();
  const month = now.getUTCMonth();
  const day = now.getUTCDate();
  const startUtcDay = Date.UTC(yer, month, day, 0, 0, 0, 0);
  const dayProgress = Math.min(
    1,
    Math.max(0, (now.getTime() - startUtcDay) / MS_DAY),
  );

  const nextIso = new Date(now.getTime() + msLeft).toISOString().slice(0, 10);

  const ariaLabel = `${hours} hours, ${minutes} minutes, ${seconds} seconds until the next drop at midnight UTC`;

  return (
    <div
      className={styles.dropCountdown}
      role="timer"
      aria-live="polite"
      aria-label={ariaLabel}
    >
      <div className={styles.dropCountRow}>
        <div className={styles.dropSeg}>{pad2(hours)}</div>
        <span className={styles.dropSep} aria-hidden>
          :
        </span>
        <div className={styles.dropSeg}>{pad2(minutes)}</div>
        <span className={styles.dropSep} aria-hidden>
          :
        </span>
        <div className={styles.dropSeg}>{pad2(seconds)}</div>
      </div>
      <div className={styles.dropProgress} aria-hidden>
        <div
          className={styles.dropProgressFill}
          style={{ width: `${dayProgress * 100}%` }}
        />
      </div>
      <div className={styles.dropSub}>Until 03:00 UTC · {nextIso}</div>
    </div>
  );
};

type SummaryFeedback = {
  liked: boolean | null;
  description: string;
  saving: boolean;
  error: string | null;
};

const DESCRIPTION_DEBOUNCE_MS = 600;

const Home: FC = () => {
  const { user } = useAuth();
  const [summaryPayload, setSummaryPayload] =
    useState<UserSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [detailItem, setDetailItem] = useState<SummaryListItem | null>(null);
  const [feedbackBySummaryId, setFeedbackBySummaryId] = useState<
    Record<string, SummaryFeedback>
  >({});
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [todayStories, setTodayStories] = useState<number | null>(null);
  const [allTimeStories, setAllTimeStories] = useState<number | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const modalCloseRef = useRef<HTMLButtonElement>(null);
  const descriptionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  const fetchSummaryPage = useCallback(async (page: number) => {
    setLoading(true);
    setFetchError(null);
    try {
      const payload = await getUserSummaryPage(page, PAGE_SIZE);
      setSummaryPayload(payload);
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : "Could not load summary");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleDeleteSummary = useCallback(
    async (e: React.MouseEvent, id: string) => {
      e.stopPropagation();
      try {
        await deleteUserSummary(id);
        const currentPage = summaryPayload?.page ?? 1;
        const isLastOnPage =
          (summaryPayload?.items.length ?? 0) === 1 && currentPage > 1;
        fetchSummaryPage(isLastOnPage ? currentPage - 1 : currentPage);
      } catch {
        // deletion failed silently; page stays unchanged
      }
    },
    [fetchSummaryPage, summaryPayload],
  );

  useEffect(() => {
    fetchSummaryPage(1);
  }, [fetchSummaryPage]);

  useEffect(() => {
    (async () => {
      try {
        const stats = await getTodayStats();
        setTodayStories(stats.stories_today);
      } catch (e) {
        // Failed to fetch stats, will show null
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const stats = await getAllTimeStats();
        setAllTimeStories(stats.stories_all_time);
      } catch (e) {
        // Failed to fetch stats, will show null
      }
    })();
  }, []);

  useEffect(() => {
    if (!detailItem) return;

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    modalCloseRef.current?.focus();

    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") setDetailItem(null);
    };

    window.addEventListener("keydown", onKey);

    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [detailItem]);

  const exportToCsv = async () => {
    setExporting(true);
    setExportError(null);
    try {
      await downloadSummariesCsv();
    } catch (e) {
      setExportError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const importFromCsv = async (file: File) => {
    setImporting(true);
    setImportError(null);
    setImportMessage(null);
    try {
      const result = await uploadSummariesCsv(file);
      setImportMessage(
        `Imported ${result.summaries_imported} summaries` +
          (result.scores_imported
            ? ` and ${result.scores_imported} scores`
            : "") +
          ".",
      );
      await fetchSummaryPage(1);
    } catch (e) {
      setImportError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  const onImportFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset the input so re-selecting the same file fires change again.
    e.target.value = "";
    if (file) void importFromCsv(file);
  };

  const persistScore = useCallback(
    async (summaryId: string, liked: boolean, description: string) => {
      const numericId = Number(summaryId);

      if (!Number.isInteger(numericId) || numericId <= 0) return;

      setFeedbackBySummaryId((prev) => {
        const current = prev[summaryId] ?? {
          liked,
          description,
          saving: false,
          error: null,
        };
        return {
          ...prev,
          [summaryId]: { ...current, saving: true, error: null },
        };
      });
      try {
        await putScore(
          numericId,
          liked,
          description.trim() ? description : null,
        );
        setFeedbackBySummaryId((prev) => {
          const current = prev[summaryId];
          if (!current) return prev;
          return {
            ...prev,
            [summaryId]: { ...current, saving: false, error: null },
          };
        });
      } catch (e) {
        const message =
          e instanceof Error ? e.message : "Could not save your feedback";
        setFeedbackBySummaryId((prev) => {
          const current = prev[summaryId];
          if (!current) return prev;
          return {
            ...prev,
            [summaryId]: { ...current, saving: false, error: message },
          };
        });
      }
    },
    [],
  );

  const setDetailVote = (liked: boolean) => {
    if (!detailItem) return;

    const summaryId = detailItem.id;

    if (descriptionTimerRef.current != null) {
      clearTimeout(descriptionTimerRef.current);
      descriptionTimerRef.current = null;
    }

    setFeedbackBySummaryId((prev) => {
      const current = prev[summaryId] ?? {
        liked: null,
        description: "",
        saving: false,
        error: null,
      };
      return { ...prev, [summaryId]: { ...current, liked } };
    });

    const existing = feedbackBySummaryId[summaryId];
    const description = existing?.description ?? "";
    persistScore(summaryId, liked, description);
  };

  const setDetailDescription = (description: string) => {
    if (!detailItem) return;

    const summaryId = detailItem.id;
    setFeedbackBySummaryId((prev) => {
      const current = prev[summaryId] ?? {
        liked: null,
        description: "",
        saving: false,
        error: null,
      };
      return { ...prev, [summaryId]: { ...current, description } };
    });

    const existing = feedbackBySummaryId[summaryId];
    const liked = existing?.liked;
    if (liked === undefined || liked === null) return;
    if (descriptionTimerRef.current != null) {
      clearTimeout(descriptionTimerRef.current);
    }

    descriptionTimerRef.current = setTimeout(() => {
      descriptionTimerRef.current = null;
      persistScore(summaryId, liked, description);
    }, DESCRIPTION_DEBOUNCE_MS);
  };

  useEffect(() => {
    return () => {
      if (descriptionTimerRef.current != null) {
        clearTimeout(descriptionTimerRef.current);
        descriptionTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!detailItem) return;

    const summaryId = detailItem.id;

    if (feedbackBySummaryId[summaryId] !== undefined) return;

    const numericId = Number(summaryId);

    if (!Number.isInteger(numericId) || numericId <= 0) return;

    let cancelled = false;

    (async () => {
      try {
        const score = await getScore(numericId);
        if (cancelled) return;
        setFeedbackBySummaryId((prev) => {
          if (prev[summaryId] !== undefined) return prev;
          return {
            ...prev,
            [summaryId]: {
              liked: score?.value ?? null,
              description: score?.description ?? "",
              saving: false,
              error: null,
            },
          };
        });
      } catch {}
    })();

    return () => {
      cancelled = true;
    };
  }, [detailItem, feedbackBySummaryId]);

  const todayIso = new Date().toISOString().slice(0, 10);
  const listDateLabel = formatListDate(todayIso);
  const name = String(user?.username ?? "user");
  const total = summaryPayload?.total ?? 0;
  const page = summaryPayload?.page ?? 1;
  const totalPages = summaryPayload?.total_pages ?? 0;
  const readyLabel =
    summaryPayload && totalPages > 0
      ? `${summaryPayload.items.length} / ${PAGE_SIZE} on this page`
      : loading && !summaryPayload
        ? "…"
        : "0 rows";

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
            TODAY<u>{todayStories ?? (loading ? "…" : 0)} stories</u>
          </div>
        </div>
        <div className={styles.mastCell}>
          <div className={styles.kvLabel}>
            ALL TIME<u>{allTimeStories ?? (loading ? "…" : 0)}</u>
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
        <p className={`${styles.metaLine} ${styles.emptyPanel}`}>
          Loading summaries…
        </p>
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
                      #
                      <b>
                        {String(idx + 1 + (page - 1) * PAGE_SIZE).padStart(
                          2,
                          "0",
                        )}
                      </b>
                    </div>
                    <div>
                      <h2 className={styles.rowTitle}>{it.title}</h2>
                      <p className={styles.rowBody}>{previewPlain(it.body)}</p>
                    </div>
                    <div className={styles.rowMeta}>
                      <span>SUMMARY</span>
                      ROW {it.id}
                      <button
                        className={styles.rowDel}
                        onClick={(e) => handleDeleteSummary(e, it.id)}
                        aria-label="Delete summary"
                      >
                        × DEL
                      </button>
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
                        {" "}
                        · latest{" "}
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
                  disabled={
                    loading || !summaryPayload || summaryPayload.page <= 1
                  }
                  onClick={() => fetchSummaryPage(summaryPayload.page - 1)}
                >
                  ← PREV
                </button>
                <button
                  type="button"
                  className={styles.swBtn}
                  disabled={
                    loading ||
                    !summaryPayload ||
                    summaryPayload.page >= summaryPayload.total_pages
                  }
                  onClick={() => fetchSummaryPage(summaryPayload.page + 1)}
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
                  disabled={loading || exporting || total === 0}
                  onClick={() => void exportToCsv()}
                >
                  {exporting ? "EXPORTING…" : "EXPORT TO CSV →"}
                </button>
                <button
                  type="button"
                  className={styles.swBtn}
                  disabled={loading || importing}
                  onClick={() => importInputRef.current?.click()}
                >
                  {importing ? "IMPORTING…" : "← IMPORT FROM CSV"}
                </button>
                <input
                  ref={importInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  hidden
                  onChange={onImportFileChange}
                />
              </div>
              {exportError ? (
                <p className={styles.error} role="alert">
                  {exportError}
                </p>
              ) : null}
              {importError ? (
                <p className={styles.error} role="alert">
                  {importError}
                </p>
              ) : null}
              {importMessage ? (
                <p className={styles.note}>{importMessage}</p>
              ) : null}
            </div>
          </div>
        </>
      ) : null}

      {detailItem
        ? (() => {
            const feedback =
              feedbackBySummaryId[detailItem.id] ??
              ({
                liked: null,
                description: "",
                saving: false,
                error: null,
              } as SummaryFeedback);
            const voteLocked =
              feedback.liked === null || feedback.liked === undefined;

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
                      <h2
                        id="summary-modal-title"
                        className={styles.modalTitle}
                      >
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
                    <section
                      className={styles.feedbackPanel}
                      aria-label="Summary feedback"
                    >
                      <div className={styles.feedbackTitle}>
                        Was this summary useful?
                      </div>
                      <div className={styles.feedbackActions}>
                        <button
                          type="button"
                          className={`${styles.swBtn} ${feedback.liked === true ? styles.feedbackBtnActive : ""}`}
                          onClick={() => setDetailVote(true)}
                          aria-pressed={feedback.liked === true}
                        >
                          Like
                        </button>
                        <button
                          type="button"
                          className={`${styles.swBtn} ${feedback.liked === false ? styles.feedbackBtnActive : ""}`}
                          onClick={() => setDetailVote(false)}
                          aria-pressed={feedback.liked === false}
                        >
                          Dislike
                        </button>
                      </div>
                      <label
                        htmlFor="summary-feedback-description"
                        className={styles.feedbackLabel}
                      >
                        What did you like or dislike?
                      </label>
                      <textarea
                        id="summary-feedback-description"
                        className={styles.feedbackInput}
                        placeholder={
                          voteLocked
                            ? "Like or dislike first, then add a comment..."
                            : "Write a short comment..."
                        }
                        value={feedback.description}
                        onChange={(e) => setDetailDescription(e.target.value)}
                      />
                      <div
                        className={styles.feedbackStatus}
                        role="status"
                        aria-live="polite"
                      >
                        {feedback.saving ? "Saving…" : null}
                        {feedback.error ? `Error: ${feedback.error}` : null}
                        {!feedback.saving &&
                        !feedback.error &&
                        feedback.liked !== null
                          ? "Saved"
                          : null}
                      </div>
                    </section>
                  </div>
                </div>
              </div>
            );
          })()
        : null}
    </>
  );
};

export default Home;
