### Frontend Deployment to Railway (Vite + React + Caddy)

This project is prepared to deploy the Vite + React frontend on Railway using Caddy to serve the built app, inspired by the template and guide:

- Template: [brody192/vite-react-template](https://github.com/brody192/vite-react-template)
- One‑click Railway page: [Deploy Vite + React](https://railway.com/deploy/NeiLty)

---

### What’s included
- `Caddyfile` – Serves `dist` with SPA fallback and compression.
- `env.example` – Documents `VITE_API_BASE` for API calls.
- `package.json` – Adds `start:caddy` script for production.

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

### Deploy on Railway (recommended for this repo)
1) Push your latest changes to GitHub.
2) On Railway: New Project → Deploy from GitHub → select this repo.
3) In Service Settings:
   - Root directory: `frontend`
   - Build command: `npm ci && npm run build`
   - Start command: `npm run start:caddy`
   - Variables:
     - `NODE_ENV=production`
     - `VITE_API_BASE=https://your-backend.example.com`
4) Trigger a deploy and wait until the service is healthy.
5) Open the generated URL. Add a custom domain in Railway → Domains (HTTPS is automatic).

Notes:
- SPA routing is handled by `try_files {path} /index.html` in `Caddyfile`.
- Compression is enabled via `encode zstd gzip`.

---

### Troubleshooting
- Blank page on refresh/deep link → Confirm `Caddyfile` exists and `try_files {path} /index.html` is present.
- 404s for API calls → Ensure `VITE_API_BASE` is set in Railway Variables and used by the app.
- Wrong service root → Ensure the service root is `frontend` (monorepo layout).
