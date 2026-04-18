import { useAuth } from '../AuthContext';
import type { CSSProperties, FC } from 'react';

const buttonStyle: CSSProperties = {
  padding: '6px 12px',
  borderRadius: 6,
  border: '1px solid #ccc',
  background: '#fff',
  cursor: 'pointer',
};

const Header: FC = () => {
  const { user, logout } = useAuth();

  return (
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', borderBottom: '1px solid #eee' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <img
          src={user?.avatarUrl as string || '/default-avatar.png'}
          alt="avatar"
          style={{ width: 40, height: 40, borderRadius: '50%', objectFit: 'cover', background: '#f3f3f3' }}
        />
        <div>
          {user ? (
            <div style={{ fontWeight: 600 }}>{user.username as string}</div>
          ) : (
            <div style={{ color: '#666' }}>Not signed in</div>
          )}
        </div>
      </div>

      <div>
        {user ? (
          <button onClick={logout} style={buttonStyle}>Logout</button>
        ) : (
          <a href="/login"><button style={buttonStyle}>Login</button></a>
        )}
      </div>
    </header>
  );
};

export default Header;
