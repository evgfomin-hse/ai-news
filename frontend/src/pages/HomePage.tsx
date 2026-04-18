import type { CSSProperties, FC } from 'react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

const LOREM_NEWS =
  'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.';

const btn: CSSProperties = {
  display: 'inline-block',
  padding: '10px 18px',
  borderRadius: 8,
  border: '1px solid #ccc',
  background: '#fff',
  cursor: 'pointer',
  textDecoration: 'none',
  color: '#111',
  fontSize: 15,
};

const HomePage: FC = () => {
  const [newsBody, setNewsBody] = useState<string | null>(null);

  return (
    <main style={{ maxWidth: 560, margin: '0 auto', padding: '24px 16px 48px' }}>
      <h1 style={{ marginTop: 0, fontSize: '1.75rem' }}>Home</h1>
      <p style={{ color: '#444', marginBottom: 20 }}>You are signed in.</p>

      <nav style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Link to="/settings" style={btn}>
          Settings
        </Link>
      </nav>

      <section style={{ marginTop: 36, paddingTop: 24, borderTop: '1px solid #eee' }}>
        <h2 style={{ fontSize: '1.15rem', marginBottom: 12 }}>News</h2>
        <p style={{ color: '#666', fontSize: 14, marginBottom: 12 }}>
          Load a sample update (placeholder content).
        </p>
        <button type="button" style={btn} onClick={() => setNewsBody(LOREM_NEWS)}>
          Receive news
        </button>
        {newsBody ? (
          <article
            style={{
              marginTop: 20,
              padding: 16,
              background: '#fafafa',
              borderRadius: 8,
              border: '1px solid #eee',
              lineHeight: 1.55,
              color: '#222',
            }}
          >
            {newsBody}
          </article>
        ) : null}
      </section>
    </main>
  );
};

export default HomePage;
