import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../../features/Auth/AuthProvider';
import type { FC } from 'react';

function Logo() {
  return (
    <div className="logo" aria-label="AI News">
      <span className="logo-bracket">[</span>
      <span className="logo-a">AI</span>
      <span className="logo-dot">·</span>
      <span className="logo-n">news</span>
      <span className="logo-bracket">]</span>
    </div>
  );
}

const Header: FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();

  const crumb = !user ? 'signin' : location.pathname === '/settings' ? 'settings' : 'home';

  return (
    <header className="topbar">
      <div className="topbar-left">
        <Logo />
        <span className="crumb">
          <span className="dim">~/</span>
          <span className="ln">ai-news</span>
          <span className="dim">/</span>
          <span className="ln">{crumb}</span>
        </span>
      </div>
      <div className="topbar-right">
        {user ? (
          <>
            <img
              src={(user.avatarUrl as string) || '/default-avatar.png'}
              alt=""
              width={28}
              height={28}
              style={{ borderRadius: '50%', objectFit: 'cover', border: '1px solid var(--line)' }}
            />
            <Link to="/" className="btn-ghost">
              home
            </Link>
            <Link to="/settings" className="btn-ghost">
              settings
            </Link>
            <button type="button" className="btn-ghost" onClick={() => void logout()}>
              logout
            </button>
          </>
        ) : null}
      </div>
    </header>
  );
};

export default Header;
