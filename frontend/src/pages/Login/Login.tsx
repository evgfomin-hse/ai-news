import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import type { FC } from 'react';
import { useState } from 'react';
import { postLogin } from '../../shared/api';
import { useAuth } from '../../features/Auth/AuthProvider';
import styles from './style.module.css';

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

      const data = await postLogin(token);

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

  return (
    <div className={styles.wrap}>
      <div className={styles.screen}>
        <div className={styles.signin}>
          <div className={styles.kicker}>Daily · AI news, quietly curated</div>
          <h1 className={styles.title}>
            Stay up to date, <em>without the hassle.</em>
          </h1>
          <p className={styles.lead}>
            One friendly digest in the world of doomscroll and information overload. Get insights without the noise.
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
