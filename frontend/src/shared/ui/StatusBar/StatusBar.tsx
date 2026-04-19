import { useEffect, useState } from 'react';
import { useAuth } from '../../../features/Auth/AuthProvider';
import styles from './style.module.css';

export default function StatusBar() {
  const { user } = useAuth();
  const [clock, setClock] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const utc = `${clock.toISOString().slice(11, 19)} UTC`;

  return (
    <footer className={styles.bar}>
      <span>
        <span className={styles.dot} aria-hidden />
        <span className={styles.strong}>Connected</span>
      </span>
      <span className={styles.sep}>·</span>
      <span className={styles.muted}>Transport · Telegram</span>
      {user ? (
        <>
          <span className={styles.sep}>·</span>
          <span className={`${styles.muted} hide-sm`}>
            Session · <span className={styles.strong}>{String(user.username ?? 'user')}</span>
          </span>
        </>
      ) : null}
      <span className={styles.spacer} />
      <span className={styles.muted}>{utc}</span>
    </footer>
  );
}
