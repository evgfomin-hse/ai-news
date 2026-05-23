# Frontend — HSE AI News

React 19 + TypeScript + Vite.

## Requirements

- Node 24

## Quick start

```bash
# 1. Copy env example and fill in the marked values
cp .env.example .env
# Required: VITE_APP_CLIENT_ID
#   (same Google OAuth 2.0 Web client ID as backend GOOGLE_CLIENT_ID)

# 2. Install deps
npm install

# 3. Run the dev server
npm run dev
```

The dev server is at <http://127.0.0.1:5173>. API calls go through the Vite proxy at `/api` → `http://127.0.0.1:8000` (configured in `vite.config.ts`), so HttpOnly session cookies work without CORS.

## Scripts

- `npm run dev` — Vite dev server with HMR
- `npm run build` — type-check + production build
- `npm run lint` — ESLint
- `npm run preview` — serve the production build locally

## Notes

- Sign-In silently breaks if `VITE_APP_CLIENT_ID` is unset; the value must match the backend's `GOOGLE_CLIENT_ID`.
- The backend must be running for API calls; start it first per `backend/README.md`.
