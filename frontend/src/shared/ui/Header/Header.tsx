import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../../features/Auth/AuthProvider';
import type { FC } from 'react';
import styles from './style.module.css';

function formatIssueDate(d: Date): string {
  return d
    .toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
    .toUpperCase();
}

const Header: FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const isSettings = location.pathname === '/settings';

  if (!user) {
    return (
      <header className={`${styles.topbar} ${styles.topbarEditorial}`}>
        <div className={styles.left}>
          <div className={styles.logoEd} aria-label="AI News">
            ai<span className={styles.dotEd}>.</span>news
          </div>
          <div className={styles.metaEd}>Sign in</div>
        </div>
      </header>
    );
  }

  if (isSettings) {
    return (
      <header className={`${styles.topbar} ${styles.topbarEditorial}`}>
        <div className={styles.left}>
          <Link to="/" className={styles.logoEd} aria-label="AI News home">
            ai<span className={styles.dotEd}>.</span>news
          </Link>
          <div className={styles.metaEd}>Your account</div>
        </div>
        <div className={styles.right}>
          <button type="button" className={`${styles.pill} ${styles.pillGhost}`} onClick={() => logout()}>
            Logout
          </button>
        </div>
      </header>
    );
  }

  const issueLine = `ISSUE · ${formatIssueDate(new Date())}`;

  return (
    <header className={`${styles.topbar} ${styles.topbarSwiss}`}>
      <div className={styles.gridSw}>
        <Link to="/" className={styles.logoSw} aria-label="AI News home">
          AI<span className={styles.dotSw}>/</span>NEWS
        </Link>
        <div className={styles.centerSw}>{issueLine}</div>
        <div className={styles.rightSwiss}>
          {user.avatarUrl ? (
            <img
              src={user.avatarUrl}
              alt=""
              width={28}
              height={28}
              className={`${styles.avatar} ${styles.avatarSw}`}
            />
          ) : null}
          <Link to="/settings" className={styles.pillSwiss}>
            SETTINGS
          </Link>
          <button type="button" className={`${styles.pillSwiss} ${styles.pillSwissSolid}`} onClick={() => logout()}>
            LOGOUT
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
