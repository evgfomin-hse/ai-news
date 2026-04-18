import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import type { FC } from 'react';
import { useState } from 'react';
import { apiUrl } from '../api';
import { useAuth } from '../AuthContext';

const LoginPage: FC = () => {
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoginSuccess = async (credentialResponse: CredentialResponse) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(apiUrl('/auth/google-login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ token: credentialResponse.credential }),
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      const data = await response.json();

      login({
        user: {
          id: data.user.id,
          username: data.user.username,
          email: data.user.email,
          avatarUrl: data.user.avatarUrl,
        },
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      console.error('Login Error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoginError = () => {
    setError('Login Failed');
    console.log('Login Failed');
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: '#f5f5f5',
      }}
    >
      <div
        style={{
          backgroundColor: '#fff',
          padding: '40px',
          borderRadius: '8px',
          boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
          textAlign: 'center',
        }}
      >
        <h1 style={{ marginBottom: '30px', color: '#333' }}>Sign In</h1>
        {error && (
          <div
            style={{
              marginBottom: '20px',
              padding: '10px',
              backgroundColor: '#fee',
              color: '#c33',
              borderRadius: '4px',
              fontSize: '14px',
            }}
          >
            {error}
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'center', opacity: isLoading ? 0.6 : 1, pointerEvents: isLoading ? 'none' : 'auto' }}>
          <GoogleLogin
            onSuccess={handleLoginSuccess}
            onError={handleLoginError}
            text="signin_with"
            theme="outline"
            size="large"
          />
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
