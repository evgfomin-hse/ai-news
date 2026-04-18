import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import type { FC } from 'react';
import { useEffect, useState } from 'react';
import { apiUrl } from '../api';
import { useAuth } from '../AuthContext';

const TODAY = new Date().toISOString().slice(0, 10);

const LoginPage: FC = () => {
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState('');

  useEffect(() => {
    const target = '$ auth --provider=google --scope=read:news';
    let i = 0;
    const iv = setInterval(() => {
      i += 1;
      setTyped(target.slice(0, i));
      if (i >= target.length) clearInterval(iv);
    }, 35);
    return () => clearInterval(iv);
  }, []);

  const handleLoginSuccess = async (credentialResponse: CredentialResponse) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(apiUrl('/auth/google-login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ token: credentialResponse.credential }),
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      const data = await response.json();

      login({
        user: {
          id: data.user.id,
          username: data.user.username,
          email: data.user.email,
          avatarUrl: data.user.avatarUrl,
        },
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      console.error('Login Error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoginError = () => {
    setError('Login Failed');
  };

  return (
    <div className="signin">
      <div className="signin-grid">
        <section className="signin-left">
          <div className="kicker">
            <span className="blink">▊</span> daily brief · ingested overnight
          </div>
          <h1 className="hero">
            A terminal
            <br />
            for everything
            <br />
            shipping in AI.
          </h1>
          <p className="lead">
            <span className="accent">AI News</span> reads the firehose so you don&apos;t. Tell it
            what you care about, wake up to a signed-off brief in your inbox or Telegram.
          </p>
          <div className="ascii-block">
            {`╭──────────────────────────────────────────╮
│  today's digest · ${TODAY}              │
│  ──────────────────────────────────────  │
│  06:14  foundation-models    opus 4      │
│  08:02  silicon              tsmc n2     │
│  11:40  robotics             figure 03   │
│  13:55  open-source          mistral     │
│  15:20  policy               eu ai act   │
│  17:08  consumer-apps        perplexity  │
╰──────────────────────────────────────────╯`}
          </div>
          <div className="stats">
            <div className="stat">
              <div className="stat-v">—</div>
              <div className="stat-k">sources scanned</div>
            </div>
            <div className="stat">
              <div className="stat-v">—</div>
              <div className="stat-k">avg read time</div>
            </div>
            <div className="stat">
              <div className="stat-v">00:00</div>
              <div className="stat-k">summaries (UTC)</div>
            </div>
          </div>
        </section>

        <section className="signin-right">
          <div className="auth-card">
            <div className="auth-head">
              <span className="dot dot-r" />
              <span className="dot dot-y" />
              <span className="dot dot-g" />
              <span className="auth-title">sign_in.sh</span>
            </div>
            <pre className="auth-term">
              <span className="dim">#!/bin/sh</span>
              {'\n'}
              <span className="dim"># authenticate to ai-news</span>
              {'\n'}
              {'\n'}
              <span className="accent">{typed}</span>
              <span className="blink">▊</span>
            </pre>
            {error ? (
              <p
                style={{
                  margin: '0 14px 10px',
                  padding: '10px 12px',
                  background: 'oklch(0.70 0.16 25 / 0.12)',
                  border: '1px solid oklch(0.40 0.10 25)',
                  borderRadius: 6,
                  fontSize: 12,
                  color: 'oklch(0.78 0.14 25)',
                }}
              >
                {error}
              </p>
            ) : null}
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                opacity: isLoading ? 0.6 : 1,
                pointerEvents: isLoading ? 'none' : 'auto',
                margin: '0 14px',
              }}
            >
              <GoogleLogin
                onSuccess={handleLoginSuccess}
                onError={handleLoginError}
                text="continue_with"
                theme="filled_black"
                size="large"
                width="100%"
              />
            </div>
            <div className="auth-foot">
              <span className="dim">by continuing you accept</span>{' '}
              <span className="ln-underline">/terms</span>
              {' · '}
              <span className="ln-underline">/privacy</span>
            </div>
          </div>
          <div className="sidecard">
            <div className="sidecard-row">
              <span className="dim">status</span>
              <span>
                <span className="dot-live" /> api reachable
              </span>
            </div>
            <div className="sidecard-row">
              <span className="dim">stack</span>
              <span>fastapi · react · postgres</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default LoginPage;
