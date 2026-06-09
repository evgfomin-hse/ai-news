import type { FC, ReactNode } from 'react';
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { Link } from 'react-router-dom';
import {
  getInterest,
  getTransport,
  parseFastApiDetail,
  patchInterest,
  patchTransport,
  postTelegramCaptureMessage,
  postTelegramTest,
  postTransportSendMessage,
  type InterestView,
  type TransportView,
} from '../../shared/api';
import { useAuth } from '../../features/Auth/AuthProvider';
import styles from './style.module.css';

function Panel({
  lab,
  title,
  hint,
  children,
}: {
  lab: string;
  title: ReactNode;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className={styles.card}>
      <div className={styles.lab}>{lab}</div>
      <h3 className={styles.cardTitle}>{title}</h3>
      {hint ? <p className={styles.hint}>{hint}</p> : null}
      {children}
    </section>
  );
}

function Row({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className={styles.kv}>
      <b className={styles.kvKey}>{k}</b>
      <span>{v}</span>
    </div>
  );
}

const HELLO_POLL_MS = 2500;
const HELLO_MAX_POLLS = 48;

const Settings: FC = () => {
  const { user } = useAuth();
  const [transport, setTransport] = useState<TransportView | null>(null);
  const [interestRow, setInterestRow] = useState<InterestView | null>(null);
  const [interestsDraft, setInterestsDraft] = useState('');
  const [tokenInput, setTokenInput] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingInterests, setSavingInterests] = useState(false);
  const [testing, setTesting] = useState(false);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [helloSession, setHelloSession] = useState<{
    botUsername: string | null;
  } | null>(null);
  const [helloHint, setHelloHint] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollAttemptsRef = useRef(0);

  const loadTransport = useCallback(async () => {
    const data = await getTransport();
    if (!data) {
      setTransport(null);
      return;
    }
    setTransport(data);
    setChatInput(data.telegramChatId ?? '');
  }, []);

  const loadInterests = useCallback(async () => {
    const data = await getInterest();
    if (!data) {
      setInterestRow(null);
      setInterestsDraft('');
      return;
    }
    setInterestRow(data);
    setInterestsDraft(data.interests ?? '');
  }, []);

  const clearHelloPoll = useCallback(() => {
    if (pollTimerRef.current != null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollAttemptsRef.current = 0;
    setHelloSession(null);
    setHelloHint(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        await Promise.all([loadTransport(), loadInterests()]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadTransport, loadInterests]);

  useEffect(() => () => clearHelloPoll(), [clearHelloPoll]);

  const persistTransportPatch = async (body: Record<string, string>) => {
    const next = await patchTransport(body);
    setTransport(next);
  };

  const saveToken = async () => {
    clearHelloPoll();
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      await persistTransportPatch({ telegramBotToken: tokenInput });
      setTokenInput('');
      setMessage('Telegram bot token saved.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const saveChatId = async () => {
    clearHelloPoll();
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      await persistTransportPatch({ telegramChatId: chatInput.trim() });
      setMessage('Chat id saved.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const clearToken = async () => {
    clearHelloPoll();
    setTokenInput('');
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      await persistTransportPatch({ telegramBotToken: '' });
      setChatInput('');
      setMessage('Token removed (chat id cleared too).');
    } catch {
      setError('Could not clear token');
    } finally {
      setSaving(false);
    }
  };

  const pollCaptureHelloOnce = useCallback(async (): Promise<'retry' | 'done'> => {
    const { response, body } = await postTelegramCaptureMessage();

    if (response.status === 409 || !response.ok) {
      clearHelloPoll();
      setError(parseFastApiDetail(body));
      return 'done';
    }

    if (body.linked && body.chatId) {
      if (pollTimerRef.current != null) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      pollAttemptsRef.current = 0;
      setHelloSession(null);
      setHelloHint(null);
      setTransport((prev) =>
        prev
          ? { ...prev, telegramChatId: body.chatId as string }
          : {
              transportId: null,
              telegramConfigured: true,
              telegramChatId: body.chatId as string,
            },
      );
      setChatInput(body.chatId);
      setMessage(`Linked your chat automatically. Chat id: ${body.chatId}`);
      setError(null);
      void loadTransport();
      return 'done';
    }

    setHelloHint(body.hint ?? 'Waiting for hello…');
    pollAttemptsRef.current += 1;

    if (pollAttemptsRef.current >= HELLO_MAX_POLLS) {
      clearHelloPoll();
      setError(
        'Timed out waiting for a hello message. Try Test bot again or paste chat id manually.',
      );
      return 'done';
    }

    return 'retry';
  }, [clearHelloPoll, loadTransport]);

  const testTelegram = async () => {
    clearHelloPoll();
    setTesting(true);
    setError(null);
    setMessage(null);
    const hadChatId = Boolean(transport?.telegramChatId);

    try {
      const response = await postTelegramTest();

      if (hadChatId) {
        setMessage(
          `Telegram OK — @${response.botUsername ?? '?'} (id ${response.botId ?? '?'})`,
        );
        return;
      }

      setHelloSession({ botUsername: response.botUsername ?? null });
      setHelloHint(
        'Send the exact message hello (lowercase) to your bot in Telegram.',
      );
      setMessage(
        `Bot @${response.botUsername ?? '…'} is reachable. Follow the steps below — we check every few seconds for your hello.`,
      );
      pollAttemptsRef.current = 0;

      const first = await pollCaptureHelloOnce();

      if (first === 'retry') {
        pollTimerRef.current = setInterval(() => {

          (async () => {
            const again = await pollCaptureHelloOnce();
            if (again !== 'retry' && pollTimerRef.current != null) {
              clearInterval(pollTimerRef.current);
              pollTimerRef.current = null;
            }
          })();
        }, HELLO_POLL_MS);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  const saveInterests = async () => {
    setSavingInterests(true);
    setError(null);
    setMessage(null);

    try {
      const data = await patchInterest(interestsDraft);
      setInterestRow(data);
      setInterestsDraft(data.interests ?? '');
      setMessage('Interests saved.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSavingInterests(false);
    }
  };

  const sendTestMessage = async () => {
    setSending(true);
    setError(null);
    setMessage(null);

    try {
      const j = await postTransportSendMessage('Test message from HSE repos.');
      setMessage(
        `Message sent (Telegram message id ${j.telegramMessageId ?? '?'})`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Send failed');
    } finally {
      setSending(false);
    }
  };

  const chatDisplay = transport?.telegramChatId
    ? transport.telegramChatId.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
    : null;

  return (
    <div className={styles.page}>
      <div className={styles.screen}>
        <div className={styles.body}>
          <Link to="/" className={styles.back}>
            ← Back to home
          </Link>
          <h1 className={styles.title}>Settings</h1>
          <p className={styles.lede}>How your letter gets written and where it lands.</p>

          <Panel lab="Profile" title="Who's reading">
            {loading ? (
              <p className={styles.dim}>Loading…</p>
            ) : (
              <>
                <Row k="Display" v={user?.username ?? '—'} />
                <Row k="Email" v={user?.email ?? '—'} />
              </>
            )}
          </Panel>

          <Panel
            lab={
              interestRow?.interestId != null
                ? `Interests · row ${interestRow.interestId}`
                : 'Interests · courseworks.interests'
            }
            title={
              <>
                What should we read <em>for you?</em>
              </>
            }
            hint="A plain list of topics — one per line, or comma-separated. Write in any language; we understand. This is the single source of truth your nightly summary is built from."
          >
            {loading ? (
              <p className={styles.dim}>Loading…</p>
            ) : (
              <>
                <textarea
                  className={styles.textarea}
                  value={interestsDraft}
                  onChange={(e) => setInterestsDraft(e.target.value)}
                  rows={6}
                  placeholder="e.g. machine learning, hiking, cinema…"
                />
                <div className={styles.btnRow}>
                  <button
                    type="button"
                    className={`${styles.btn} ${styles.btnPrime}`}
                    disabled={
                      savingInterests ||
                      interestsDraft === (interestRow?.interests ?? '')
                    }
                    onClick={() => void saveInterests()}
                  >
                    {savingInterests ? 'Saving…' : 'Save interests'}
                  </button>
                  <button
                    type="button"
                    className={`${styles.btn} ${styles.btnGhost}`}
                    onClick={() => setInterestsDraft(interestRow?.interests ?? '')}
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}
          </Panel>

          <Panel
            lab="Transport · Telegram"
            title={
              <>
                Where it <em>lands</em>
              </>
            }
            hint="Your bot token and chat id live in transports. The server calls Telegram's sendMessage for you. Tokens are written once and never shown again after save."
          >
            {helloSession ? (
              <div className={styles.callout}>
                <strong className={styles.calloutTitle}>Link your Telegram chat</strong>
                <ol className={styles.calloutList}>
                  <li>
                    Open Telegram and find your bot{' '}
                    {helloSession.botUsername ? (
                      <strong>@{helloSession.botUsername}</strong>
                    ) : (
                      <span>(the one for this token)</span>
                    )}
                    .
                  </li>
                  <li>
                    Send exactly: <code className={styles.mono}>hello</code>
                  </li>
                  <li>Keep this page open — we poll for it.</li>
                </ol>
                {helloHint ? <p className={styles.hintLine}>{helloHint}</p> : null}
                <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={clearHelloPoll}>
                  Cancel linking
                </button>
              </div>
            ) : null}

            {loading ? (
              <p className={styles.dim}>Loading…</p>
            ) : (
              <>
                <div className={styles.tgChip}>
                  <span className={styles.tgChipDot} aria-hidden />
                  Bot token on file
                  {chatDisplay ? (
                    <>
                      {' '}
                      · chat <b>{chatDisplay}</b>
                    </>
                  ) : (
                    ' · chat not set'
                  )}
                  {transport?.transportId != null ? (
                    <span className={styles.dim}>
                      {' '}
                      · transport id {transport.transportId}
                    </span>
                  ) : null}
                </div>

                <div className={styles.kv} style={{ marginTop: 18 }}>
                  <b className={styles.kvKey}>New token</b>
                  <input
                    type="password"
                    autoComplete="off"
                    className={styles.input}
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    placeholder="Paste to replace, or leave empty to clear…"
                  />
                </div>
                <div className={styles.btnRow}>
                  <button
                    type="button"
                    className={`${styles.btn} ${styles.btnPrime}`}
                    disabled={saving || !tokenInput.trim()}
                    onClick={() => void saveToken()}
                  >
                    {saving ? 'Saving…' : 'Save token'}
                  </button>
                  <button
                    type="button"
                    className={styles.btn}
                    disabled={
                      testing ||
                      !transport?.telegramConfigured ||
                      Boolean(helloSession)
                    }
                    onClick={() => void testTelegram()}
                  >
                    {testing ? 'Testing…' : 'Test bot'}
                  </button>
                  <button
                    type="button"
                    className={`${styles.btn} ${styles.btnWarn}`}
                    disabled={saving || !transport?.telegramConfigured}
                    onClick={() => void clearToken()}
                  >
                    Clear token
                  </button>
                </div>
                <div className={styles.status}>
                  <span className={styles.statusDot} aria-hidden />
                  <span>
                    <span className={styles.statusStrong}>Ready</span>
                    {' · '}
                    <span className={styles.dim}>Telegram transport</span>
                  </span>
                </div>

                <div className={styles.subsection}>
                  <div className={styles.lab}>Chat id</div>
                  <h3 className={styles.cardTitle}>Link your chat</h3>
                  <p className={styles.hint}>
                    Paste your chat id manually, or use Test bot without a chat to link automatically
                    after you send hello.
                  </p>
                  <div className={styles.kv}>
                    <b className={styles.kvKey}>Chat id</b>
                    <input
                      type="text"
                      inputMode="numeric"
                      autoComplete="off"
                      className={styles.input}
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="e.g. 123456789"
                    />
                  </div>
                  <div className={styles.btnRow}>
                    <button
                      type="button"
                      className={`${styles.btn} ${styles.btnPrime}`}
                      disabled={saving || chatInput.trim() === (transport?.telegramChatId ?? '')}
                      onClick={() => void saveChatId()}
                    >
                      {saving ? 'Saving…' : 'Save chat id'}
                    </button>
                  </div>
                </div>

                <div className={styles.subsection}>
                  <div className={styles.lab}>Send</div>
                  <h3 className={styles.cardTitle}>Send a test</h3>
                  <p className={styles.hint}>
                    Drops a friendly message into your Telegram so you can see how delivery feels.
                  </p>
                  <div className={styles.btnRow}>
                    <button
                      type="button"
                      className={`${styles.btn} ${styles.btnAccent}`}
                      disabled={
                        sending ||
                        !transport?.telegramConfigured ||
                        !transport?.telegramChatId
                      }
                      onClick={() => void sendTestMessage()}
                    >
                      {sending ? 'Sending…' : 'Send test message to my chat'}
                    </button>
                  </div>
                </div>

                {message ? (
                  <pre className={styles.messageBox}>{message}</pre>
                ) : null}
                {error ? (
                  <pre className={`${styles.messageBox} ${styles.messageBoxError}`}>{error}</pre>
                ) : null}
              </>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
};

export default Settings;
