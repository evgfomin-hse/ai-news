import { Link } from 'react-router-dom';
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

function Logo({ interactive }: { interactive: boolean }) {
  const mark = (
    <>
      ai<span className={styles.dotEd}>.</span>news
    </>
  );
  if (interactive) {
    return (
      <Link to="/" className={styles.logoEd} aria-label="AI News home">
        {mark}
      </Link>
    );
  }
  return (
    <div className={styles.logoEd} aria-label="AI News">
      {mark}
    </div>
  );
}

const Header: FC = () => {
  const { user, logout } = useAuth();

  if (!user) {
    return (
      <header className={`${styles.topbar} ${styles.topbarSwiss}`}>
        <div className={styles.gridSw}>
          <Logo interactive={false} />
          <div className={styles.centerSw}>SIGN IN</div>
          <div className={styles.rightSwiss} />
        </div>
      </header>
    );
  }

  const issueLine = `ISSUE · ${formatIssueDate(new Date())}`;

  return (
    <header className={`${styles.topbar} ${styles.topbarSwiss}`}>
      <div className={styles.gridSw}>
        <Logo interactive />
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
