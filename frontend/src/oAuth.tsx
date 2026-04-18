import { GoogleOAuthProvider } from '@react-oauth/google';

const clientId = import.meta.env.VITE_APP_CLIENT_ID;

function OAuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <GoogleOAuthProvider clientId={clientId}>
      {children}
    </GoogleOAuthProvider>
  );
}

export default OAuthProvider;