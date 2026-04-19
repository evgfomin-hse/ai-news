import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import type { FC } from 'react';
import { useState } from 'react';
import { postGoogleLogin } from '../../shared/api';
import { useAuth } from '../../features/Auth/AuthProvider';
import styles from './style.module.css';

function formatNavDate(d: Date): string {
  return d.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
}

const Login: FC = () => {
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoginSuccess = async (credentialResponse: CredentialResponse) => {
    setIsLoading(true);
    setError(null);

    try {
      const token = credentialResponse.credential;
      if (!token) throw new Error('Login failed');
      const data = await postGoogleLogin(token);

      login({
        user: {
          id: data.user.id,
          username: data.user.username,
          email: data.user.email,
          avatarUrl: data.user.avatarUrl ?? undefined,
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

  const navDate = formatNavDate(new Date());

  return (
    <div className={styles.wrap}>
      <div className={styles.screen}>
        <div className={styles.screenHead}>
          <div className={styles.dots} aria-hidden>
            <span className={styles.dotWin} />
            <span className={styles.dotWin} />
            <span className={styles.dotWin} />
          </div>
          <span className={styles.url}>ainews.app/signin</span>
          <span className={styles.badge}>SIGN IN</span>
        </div>
        <div className={styles.nav}>
          <div className={styles.logo} aria-hidden>
            ai<span className={styles.logoDot}>.</span>news
          </div>
          <div className={styles.meta}>Daily digest · {navDate}</div>
          <div className={styles.navRight}>
            <span className={`${styles.pill} ${styles.pillGhost}`}>About</span>
            <span className={styles.pill}>Login</span>
          </div>
        </div>
        <div className={styles.signin}>
          <div className={styles.kicker}>Daily · AI news, quietly curated</div>
          <h1 className={styles.title}>
            Your morning read, <em>without the noise.</em>
          </h1>
          <p className={styles.lead}>
            One friendly digest, built around the topics you care about. No feeds. No doomscroll.
            Just a well-made letter — with summaries from your coursework table.
          </p>
          {error ? <p className={styles.error}>{error}</p> : null}
          <div className={`${styles.gbtnWrap} ${isLoading ? styles.loading : ''}`}>
            <GoogleLogin
              onSuccess={handleLoginSuccess}
              onError={handleLoginError}
              text="continue_with"
              theme="outline"
              size="large"
              width="320"
            />
          </div>
          <div className={styles.fine}>Members-only · reads in two minutes</div>
          <div className={styles.deco}>
            <div>
              Est.<b>2026</b>
            </div>
            <div>
              Summaries<b>00:00 UTC</b>
            </div>
            <div>
              Via<b>Telegram</b>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
