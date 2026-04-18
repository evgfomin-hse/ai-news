import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './assets/reset.css'
import App from './App.tsx'
import OAuthProvider from './oAuth.tsx'
import { AuthProvider } from './AuthContext';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <OAuthProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </OAuthProvider>
  </StrictMode>,
)
