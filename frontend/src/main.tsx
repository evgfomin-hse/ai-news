import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './shared/styles/reset.css';
import './theme.css';
import App from './App.tsx';
import styles from './style.module.css';
import { AuthProvider, OAuthProvider } from './features/Auth';
import Header from './shared/ui/Header';
import StatusBar from './shared/ui/StatusBar';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <OAuthProvider>
        <AuthProvider>
          <div className={styles.root}>
            <Header />
            <App />
            <StatusBar />
          </div>
        </AuthProvider>
      </OAuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
