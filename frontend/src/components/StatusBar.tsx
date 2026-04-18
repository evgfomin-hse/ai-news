import { useEffect, useState } from 'react';
import { useAuth } from '../AuthContext';

export default function StatusBar() {
  const { user } = useAuth();
  const [clock, setClock] = useState(() => new Date());

  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const utc = `${clock.toISOString().slice(11, 19)} UTC`;

  return (
    <footer className="statusbar">
      <span>
        <span className="accent">●</span> connected
      </span>
      <span className="dim">│</span>
      <span>transport: telegram</span>
      {user ? (
        <>
          <span className="dim">│</span>
          <span className="hide-sm">
            session: <span className="ln">{String(user.username ?? 'user')}</span>
          </span>
        </>
      ) : null}
      <span className="spacer" />
      <span className="dim">│</span>
      <span>{utc}</span>
    </footer>
  );
}
