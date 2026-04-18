import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './assets/reset.css';
import './theme.css';
import './index.css';
import App from './App.tsx';
import OAuthProvider from './oAuth.tsx';
import { AuthProvider } from './AuthContext';
import Header from './components/Header';
import StatusBar from './components/StatusBar';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <OAuthProvider>
        <AuthProvider>
          <div className="root">
            <Header />
            <App />
            <StatusBar />
          </div>
        </AuthProvider>
      </OAuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
