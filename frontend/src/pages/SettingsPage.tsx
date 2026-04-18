import type { FC, ReactNode } from 'react';
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { Link } from 'react-router-dom';
import { apiUrl } from '../api';
import { useAuth } from '../AuthContext';

function Panel({
  title,
  section,
  sub,
  children,
}: {
  title: string;
  section: string;
  sub?: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <header className="panel-head">
        <span className="panel-sec">§{section}</span>
        <span className="panel-title">{title}</span>
        <span className="panel-dots">{'·'.repeat(48)}</span>
      </header>
      {sub ? <p className="panel-sub">{sub}</p> : null}
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Row({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="row">
      <div className="row-k">{k}</div>
      <div className="row-v">{v}</div>
    </div>
  );
}

type TransportMe = {
  transportId: number | null;
  telegramConfigured: boolean;
  telegramChatId: string | null;
};

type InterestMe = {
  interestId: number | null;
  interests: string;
};

const HELLO_POLL_MS = 2500;
const HELLO_MAX_POLLS = 48;

const SettingsPage: FC = () => {
  const { user } = useAuth();
  const [transport, setTransport] = useState<TransportMe | null>(null);
  const [interestRow, setInterestRow] = useState<InterestMe | null>(null);
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
    const r = await fetch(apiUrl('/transports/me'), { credentials: 'include' });
    if (!r.ok) {
      setTransport(null);
      return;
    }
    const data = (await r.json()) as TransportMe;
    setTransport(data);
    setChatInput(data.telegramChatId ?? '');
  }, []);

  const loadInterests = useCallback(async () => {
    const r = await fetch(apiUrl('/interests/me'), { credentials: 'include' });
    if (!r.ok) {
      setInterestRow(null);
      setInterestsDraft('');
      return;
    }
    const data = (await r.json()) as InterestMe;
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

  const parseDetail = (j: { detail?: unknown }): string => {
    const d = j.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) {
      return d
        .map((x) =>
          typeof x === 'object' && x && 'msg' in x
            ? String((x as { msg: string }).msg)
            : String(x),
        )
        .join(', ');
    }
    return 'Request failed';
  };

  const patchTransport = async (body: Record<string, string>) => {
    const r = await fetch(apiUrl('/transports/me'), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const j = (await r.json().catch(() => ({}))) as { detail?: unknown };
      throw new Error(parseDetail(j));
    }
    setTransport((await r.json()) as TransportMe);
  };

  const saveToken = async () => {
    clearHelloPoll();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await patchTransport({ telegramBotToken: tokenInput });
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
      await patchTransport({ telegramChatId: chatInput.trim() });
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
      await patchTransport({ telegramBotToken: '' });
      setChatInput('');
      setMessage('Token removed (chat id cleared too).');
    } catch {
      setError('Could not clear token');
    } finally {
      setSaving(false);
    }
  };

  /** `retry` = keep polling; `done` = stop (linked, fatal error, or timeout). */
  const pollCaptureHelloOnce = useCallback(async (): Promise<'retry' | 'done'> => {
    const r = await fetch(apiUrl('/transports/me/telegram-capture-hello'), {
      method: 'POST',
      credentials: 'include',
    });
    const j = (await r.json().catch(() => ({}))) as {
      linked?: boolean;
      chatId?: string;
      hint?: string;
      detail?: unknown;
    };

    if (r.status === 409 || !r.ok) {
      clearHelloPoll();
      setError(parseDetail(j));
      return 'done';
    }

    if (j.linked && j.chatId) {
      if (pollTimerRef.current != null) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      pollAttemptsRef.current = 0;
      setHelloSession(null);
      setHelloHint(null);
      setTransport((prev) =>
        prev
          ? { ...prev, telegramChatId: j.chatId as string }
          : {
              transportId: null,
              telegramConfigured: true,
              telegramChatId: j.chatId as string,
            },
      );
      setChatInput(j.chatId);
      setMessage(`Linked your chat automatically. Chat id: ${j.chatId}`);
      setError(null);
      void loadTransport();
      return 'done';
    }

    setHelloHint(j.hint ?? 'Waiting for hello…');
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
      const r = await fetch(apiUrl('/transports/me/telegram-test'), {
        method: 'POST',
        credentials: 'include',
      });
      const j = (await r.json().catch(() => ({}))) as {
        botUsername?: string;
        botId?: number;
        detail?: unknown;
      };
      if (!r.ok) {
        throw new Error(parseDetail(j));
      }

      if (hadChatId) {
        setMessage(
          `Telegram OK — @${j.botUsername ?? '?'} (id ${j.botId ?? '?'})`,
        );
        return;
      }

      setHelloSession({ botUsername: j.botUsername ?? null });
      setHelloHint(
        'Send the exact message hello (lowercase) to your bot in Telegram.',
      );
      setMessage(
        `Bot @${j.botUsername ?? '…'} is reachable. Follow the steps below — we check every few seconds for your hello.`,
      );
      pollAttemptsRef.current = 0;
      const first = await pollCaptureHelloOnce();
      if (first === 'retry') {
        pollTimerRef.current = setInterval(() => {
          void (async () => {
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
      const r = await fetch(apiUrl('/interests/me'), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ interests: interestsDraft }),
      });
      if (!r.ok) {
        const j = (await r.json().catch(() => ({}))) as { detail?: unknown };
        throw new Error(parseDetail(j));
      }
      const data = (await r.json()) as InterestMe;
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
      const r = await fetch(apiUrl('/transports/me/send-message'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          text: 'Test message from HSE repos.',
        }),
      });
      const j = (await r.json().catch(() => ({}))) as {
        telegramMessageId?: number;
        detail?: unknown;
      };
      if (!r.ok) {
        throw new Error(parseDetail(j));
      }
      setMessage(
        `Message sent (Telegram message id ${j.telegramMessageId ?? '?'})`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Send failed');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="settings">
      <div className="set-head">
        <Link to="/" className="btn-ghost">
          ← back
        </Link>
        <h2 className="h2">
          settings<span className="accent">.</span>config
        </h2>
        <span className="spacer" />
        <span className="dim small hide-sm">coursework · HSE</span>
      </div>

      <div className="set-grid">
        <Panel title="account" section="01">
          <Row k="display name" v={user?.username ?? '—'} />
          <Row k="email" v={user?.email ?? '—'} />
        </Panel>

        <Panel
          title="interests"
          section="02"
          sub="Stored in public.interests (text column)."
        >
          {loading ? (
            <p className="dim">Loading…</p>
          ) : (
            <>
              {interestRow?.interestId != null ? (
                <p className="dim small" style={{ marginBottom: 8 }}>
                  row id {interestRow.interestId}
                </p>
              ) : null}
              <textarea
                className="input"
                value={interestsDraft}
                onChange={(e) => setInterestsDraft(e.target.value)}
                rows={5}
                placeholder="e.g. machine learning, hiking, cinema…"
                style={{ maxWidth: '100%', minHeight: 120, resize: 'vertical' }}
              />
              <button
                type="button"
                className="btn-primary small"
                disabled={
                  savingInterests ||
                  interestsDraft === (interestRow?.interests ?? '')
                }
                onClick={() => void saveInterests()}
              >
                {savingInterests ? 'Saving…' : 'Save interests'}
              </button>
            </>
          )}
        </Panel>

        <Panel
          title="transport"
          section="03"
          sub="Bot token + chat id in transports.data. Token never returned after save."
        >
          {helloSession ? (
            <div className="sidecard" style={{ marginBottom: 16 }}>
              <strong style={{ display: 'block', marginBottom: 8 }}>
                Link your Telegram chat
              </strong>
              <ol
                className="dim"
                style={{
                  margin: '0 0 12px',
                  paddingLeft: 20,
                  fontSize: 13,
                  listStyle: 'decimal',
                }}
              >
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
                  Send exactly: <code className="mono">hello</code>
                </li>
                <li>Keep this page open — we poll for it.</li>
              </ol>
              {helloHint ? <p className="small" style={{ margin: '0 0 12px' }}>{helloHint}</p> : null}
              <button type="button" className="btn-secondary small" onClick={clearHelloPoll}>
                Cancel linking
              </button>
            </div>
          ) : null}

          {loading ? (
            <p className="dim">Loading…</p>
          ) : (
            <>
              <p className="tg-linked dim" style={{ marginBottom: 12 }}>
                <strong className="ln">
                  {transport?.telegramConfigured ? 'token on file' : 'no token'}
                </strong>
                {' · '}
                <strong className="ln">
                  {transport?.telegramChatId
                    ? `chat ${transport.telegramChatId}`
                    : 'chat not set'}
                </strong>
                {transport?.transportId != null ? (
                  <span className="faint"> · transport id {transport.transportId}</span>
                ) : null}
              </p>

              <Row
                k="bot token"
                v={
                  <input
                    type="password"
                    autoComplete="off"
                    className="input"
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    placeholder={
                      transport?.telegramConfigured
                        ? 'New token to replace, or clear'
                        : 'Paste from @BotFather'
                    }
                  />
                }
              />

              <div className="tg-actions">
                <button
                  type="button"
                  className="btn-secondary small"
                  disabled={saving || !tokenInput.trim()}
                  onClick={() => void saveToken()}
                >
                  {saving ? 'Saving…' : 'Save token'}
                </button>
                <button
                  type="button"
                  className="btn-secondary small"
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
                  className="btn-danger small"
                  disabled={saving || !transport?.telegramConfigured}
                  onClick={() => void clearToken()}
                >
                  Clear token
                </button>
              </div>

              <Row
                k="chat id"
                v={
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    className="input"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="e.g. 123456789"
                  />
                }
              />
              <button
                type="button"
                className="btn-secondary small"
                disabled={
                  saving || chatInput.trim() === (transport?.telegramChatId ?? '')
                }
                onClick={() => void saveChatId()}
              >
                {saving ? 'Saving…' : 'Save chat id'}
              </button>

              <div style={{ marginTop: 16 }}>
                <div className="tw-label" style={{ marginBottom: 6 }}>
                  send message
                </div>
                <button
                  type="button"
                  className="btn-primary small"
                  disabled={
                    sending ||
                    !transport?.telegramConfigured ||
                    !transport?.telegramChatId
                  }
                  onClick={() => void sendTestMessage()}
                >
                  {sending ? 'Sending…' : 'Send test to my chat'}
                </button>
              </div>

              {message ? (
                <pre className="tg-preview" style={{ marginTop: 14, color: 'var(--text)' }}>
                  {message}
                </pre>
              ) : null}
              {error ? (
                <pre
                  className="tg-preview"
                  style={{
                    marginTop: 14,
                    borderColor: 'oklch(0.40 0.10 25)',
                    color: 'oklch(0.78 0.14 25)',
                  }}
                >
                  {error}
                </pre>
              ) : null}
            </>
          )}
        </Panel>
      </div>
    </div>
  );
};

export default SettingsPage;
