### Frontend Deployment to Railway (Vite + React, Railpack by default)

This project is prepared to deploy the Vite + React frontend on Railway using Railpack (no Caddy required), aligned with the updated template:

- Template: [brody192/vite-react-template](https://github.com/brody192/vite-react-template)
- One‑click Railway page: [Deploy Vite + React](https://railway.com/deploy/NeiLty)

---

### What’s included
- `railway.json` – Uses the Railpack builder.
- `env.example` – Documents `VITE_API_BASE` for API calls.
- `package.json` – Adds `start` for Railpack (`vite preview` on `$PORT`) and keeps optional `start:caddy`.

---

### Prerequisites
- Ensure the app builds locally:

```bash
npm ci
npm run build
```

---

### Configure environment variables
- Copy `env.example` to a real environment file locally if needed (Railway uses Variables UI):

```bash
cp env.example .env
```

- Set `VITE_API_BASE` to your backend URL (e.g. `http://localhost:8000` for dev or your backend’s public URL for prod).

---

### Deploy on Railway (Railpack, recommended)
1) Push your latest changes to GitHub.
2) On Railway: New Project → Deploy from GitHub → select this repo.
3) In Service Settings:
   - Root directory: `frontend`
   - Build command: `npm ci && npm run build`
   - Start command: `npm start`
   - Variables:
     - `NODE_ENV=production`
     - `VITE_API_BASE=https://your-backend.example.com`
4) Trigger a deploy and wait until the service is healthy.
5) Open the generated URL. Add a custom domain in Railway → Domains (HTTPS is automatic).

Notes:
- SPA routing is handled by Vite preview (single-page app fallback).

---

### Optional: Caddy-based serving
If you prefer Caddy (for custom static headers or advanced routing), keep `Caddyfile` and use:
- Start command: `npm run start:caddy`
- Notes: SPA fallback via `try_files {path} /index.html`, compression via `encode zstd gzip`.

---

### Troubleshooting
- Blank page on refresh/deep link → Vite preview should already support SPA fallback; ensure the app was built and deployed from `dist/`.
- 404s for API calls → Ensure `VITE_API_BASE` is set in Railway Variables and used by the app.
- Wrong service root → Ensure the service root is `frontend` (monorepo layout).
