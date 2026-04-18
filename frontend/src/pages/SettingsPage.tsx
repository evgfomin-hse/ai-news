import type { CSSProperties, FC } from 'react';
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { Link } from 'react-router-dom';
import { apiUrl } from '../api';
import { useAuth } from '../AuthContext';

const linkBtn: CSSProperties = {
  display: 'inline-block',
  marginBottom: 24,
  padding: '8px 14px',
  borderRadius: 8,
  border: '1px solid #ccc',
  background: '#fff',
  textDecoration: 'none',
  color: '#111',
  fontSize: 14,
};

const btn: CSSProperties = {
  padding: '8px 16px',
  borderRadius: 8,
  border: '1px solid #ccc',
  background: '#fff',
  cursor: 'pointer',
  fontSize: 14,
};

type TransportMe = {
  transportId: number | null;
  telegramConfigured: boolean;
  telegramChatId: string | null;
};

const HELLO_POLL_MS = 2500;
const HELLO_MAX_POLLS = 48;

const SettingsPage: FC = () => {
  const { user } = useAuth();
  const [transport, setTransport] = useState<TransportMe | null>(null);
  const [tokenInput, setTokenInput] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
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
        await loadTransport();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadTransport]);

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
    <main style={{ maxWidth: 560, margin: '0 auto', padding: '24px 16px 48px' }}>
      <Link to="/" style={linkBtn}>
        ← Back to home
      </Link>
      <h1 style={{ marginTop: 0, fontSize: '1.75rem' }}>Settings</h1>
      <dl style={{ margin: '0 0 32px', color: '#333' }}>
        <dt style={{ fontWeight: 600, marginTop: 12 }}>Display name</dt>
        <dd style={{ margin: '4px 0 0' }}>{user?.username ?? '—'}</dd>
        <dt style={{ fontWeight: 600, marginTop: 12 }}>Email</dt>
        <dd style={{ margin: '4px 0 0' }}>{user?.email ?? '—'}</dd>
      </dl>

      <section
        style={{
          paddingTop: 24,
          borderTop: '1px solid #eee',
        }}
      >
        <h2 style={{ fontSize: '1.15rem', marginBottom: 8 }}>Transport</h2>
        <p style={{ color: '#666', fontSize: 14, marginBottom: 16 }}>
          Your bot token and chat id live in <code>transports.data</code> (
          <code>telegramBotToken</code>, <code>telegramChatId</code>). The
          server uses them to call Telegram&apos;s <code>sendMessage</code> for
          you. The token is never returned after save.
        </p>

        {helloSession ? (
          <div
            style={{
              marginBottom: 20,
              padding: 16,
              borderRadius: 10,
              border: '1px solid #90caf9',
              background: '#e3f2fd',
              color: '#0d47a1',
            }}
          >
            <strong style={{ display: 'block', marginBottom: 8 }}>
              Link your Telegram chat
            </strong>
            <ol style={{ margin: '0 0 12px', paddingLeft: 20, fontSize: 14 }}>
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
                Send exactly this text as a normal message:{' '}
                <code style={{ background: '#fff', padding: '2px 6px' }}>
                  hello
                </code>
              </li>
              <li>Keep this page open — we detect it automatically.</li>
            </ol>
            {helloHint ? (
              <p style={{ fontSize: 13, margin: '0 0 12px' }}>{helloHint}</p>
            ) : null}
            <button type="button" style={btn} onClick={clearHelloPoll}>
              Cancel linking
            </button>
          </div>
        ) : null}

        {loading ? (
          <p style={{ color: '#666' }}>Loading…</p>
        ) : (
          <>
            <p style={{ fontSize: 14, marginBottom: 12 }}>
              Status:{' '}
              <strong>
                {transport?.telegramConfigured
                  ? 'Bot token on file'
                  : 'No token saved'}
              </strong>
              {' · '}
              <strong>
                {transport?.telegramChatId
                  ? `Chat id ${transport.telegramChatId}`
                  : 'Chat id not set'}
              </strong>
              {transport?.transportId != null ? (
                <span style={{ color: '#888' }}>
                  {' '}
                  (transport id {transport.transportId})
                </span>
              ) : null}
            </p>

            <label
              style={{
                display: 'block',
                fontWeight: 600,
                fontSize: 14,
                marginBottom: 6,
              }}
            >
              Telegram bot token
            </label>
            <input
              type="password"
              autoComplete="off"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder={
                transport?.telegramConfigured
                  ? 'New token to replace, or Clear token'
                  : 'Paste token from @BotFather'
              }
              style={{
                width: '100%',
                maxWidth: 420,
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid #ccc',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 10,
                marginTop: 10,
                alignItems: 'center',
              }}
            >
              <button
                type="button"
                style={btn}
                disabled={saving || !tokenInput.trim()}
                onClick={() => void saveToken()}
              >
                {saving ? 'Saving…' : 'Save token'}
              </button>
              <button
                type="button"
                style={btn}
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
                style={{ ...btn, color: '#a33' }}
                disabled={saving || !transport?.telegramConfigured}
                onClick={() => void clearToken()}
              >
                Clear token
              </button>
            </div>

            <label
              style={{
                display: 'block',
                fontWeight: 600,
                fontSize: 14,
                marginTop: 28,
                marginBottom: 6,
              }}
            >
              Telegram chat id (optional)
            </label>
            <p style={{ color: '#666', fontSize: 13, margin: '0 0 8px' }}>
              Or paste your chat id manually. Use <strong>Test bot</strong>{' '}
              without a chat id to link automatically after you send{' '}
              <code>hello</code>.
            </p>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="e.g. 123456789"
              style={{
                width: '100%',
                maxWidth: 420,
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid #ccc',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
            <div style={{ marginTop: 10 }}>
              <button
                type="button"
                style={btn}
                disabled={
                  saving ||
                  chatInput.trim() === (transport?.telegramChatId ?? '')
                }
                onClick={() => void saveChatId()}
              >
                {saving ? 'Saving…' : 'Save chat id'}
              </button>
            </div>

            <div style={{ marginTop: 28 }}>
              <h3 style={{ fontSize: '1rem', marginBottom: 8 }}>Send message</h3>
              <button
                type="button"
                style={btn}
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

            {message ? (
              <p
                style={{
                  marginTop: 14,
                  padding: 10,
                  background: '#e8f5e9',
                  color: '#1b5e20',
                  borderRadius: 8,
                  fontSize: 14,
                }}
              >
                {message}
              </p>
            ) : null}
            {error ? (
              <p
                style={{
                  marginTop: 14,
                  padding: 10,
                  background: '#ffebee',
                  color: '#b71c1c',
                  borderRadius: 8,
                  fontSize: 14,
                }}
              >
                {error}
              </p>
            ) : null}
          </>
        )}
      </section>
    </main>
  );
};

export default SettingsPage;
