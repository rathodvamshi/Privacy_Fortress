# 🚀 Privacy Fortress — Deployment Guide

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│   Vercel (Frontend)  │  HTTPS  │   Render (Backend)    │
│   React + Vite SPA   │ ──────► │   FastAPI + Gunicorn  │
└─────────────────────┘         └──────────┬───────────┘
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                    MongoDB Atlas    Redis Cloud      Groq Cloud
                    (Database)       (Vault/Cache)    (LLM API)
```

---

## Step 1 — Push to GitHub

```bash
cd CBIT
git init
git add .
git commit -m "Privacy Fortress v1.0 — ready for deployment"
git remote add origin https://github.com/YOUR_USERNAME/privacy-fortress.git
git push -u origin main
```

> ⚠️ The `.gitignore` ensures `.env` files are **never pushed** to GitHub.

---

## Step 2 — Deploy Backend on Render

### 2A. Create a New Web Service

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your **GitHub repo**
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `privacy-fortress-api` |
| **Root Directory** | `backend` |
| **Runtime** | `Python` |
| **Build Command** | `chmod +x build.sh && ./build.sh` |
| **Start Command** | `gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120` |
| **Plan** | Free (or Starter for better performance) |

### 2B. Set Environment Variables in Render Dashboard

Go to **Environment** tab and add these:

| Key | Value |
|-----|-------|
| `MONGODB_URI` | `mongodb+srv://codehub369:ZeroLeak@cluster0.eh92scv.mongodb.net/?appName=Cluster0` |
| `GROQ_API_KEY` | `gsk_5h2sa5KVeBOXMXTYhqML...` (your full key) |
| `REDIS_URL` | `redis://default:Gg12Yku...@redis-12512.c16.us-east-1-2.ec2.cloud.redislabs.com:12512` |
| `ENCRYPTION_KEY` | `privacy-fortress-secret-key-32b` |
| `APP_SECRET` | `privacy-fortress-app-secret-2026` |
| `CORS_ORIGINS` | `https://your-app.vercel.app` ← (update after Vercel deploy) |
| `APP_ENV` | `production` |
| `PYTHON_VERSION` | `3.11.0` |

### 2C. Deploy

Click **Create Web Service**. Wait for build to complete (~3-5 min on first deploy).

Your backend URL will be: `https://privacy-fortress-api.onrender.com`

Test it: `https://privacy-fortress-api.onrender.com/health`

---

## Step 3 — Deploy Frontend on Vercel

### 3A. Import Project

1. Go to [vercel.com](https://vercel.com) → **Add New** → **Project**
2. Import your **GitHub repo**
3. Configure:

| Setting | Value |
|---------|-------|
| **Framework Preset** | `Vite` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |

### 3B. Set Environment Variable

In **Environment Variables** section:

| Key | Value |
|-----|-------|
| `VITE_API_URL` | `https://privacy-fortress-api.onrender.com` ← your Render URL |

> ⚠️ **Must start with `VITE_`** for Vite to expose it to the frontend code.

### 3C. Deploy

Click **Deploy**. First deploy takes ~1-2 minutes.

Your frontend URL will be: `https://your-app.vercel.app`

---

## Step 4 — Connect CORS (Critical!)

After both are deployed:

1. Go back to **Render Dashboard** → your service → **Environment**
2. Update `CORS_ORIGINS`:
   ```
   https://your-app.vercel.app
   ```
   (Use the exact Vercel URL, no trailing slash)
3. Click **Save Changes** → Render will auto-redeploy

---

## Step 5 — Verify

1. Open your Vercel URL
2. Sign up / Log in
3. Send a message with PII (e.g., "My name is John and my email is john@test.com")
4. Check that masking works
5. View masked prompt details

---

## Troubleshooting

### "CORS error" in browser console
→ Make sure `CORS_ORIGINS` on Render exactly matches your Vercel URL (with `https://`)

### "Failed to fetch" / Network error
→ Make sure `VITE_API_URL` on Vercel matches your Render URL (with `https://`, no trailing `/`)

### Backend 500 errors
→ Check Render logs. Most likely a missing env var.

### spaCy model not found
→ The `build.sh` should handle this. Check Render build logs for errors.

### Render free tier cold starts
→ Free tier services sleep after 15 min of inactivity. First request takes ~30-50s to wake up. Use Starter plan for always-on.

---

## Local Development

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

No `.env` needed for frontend locally (defaults to `http://localhost:8000`).

---

## File Structure for Deployment

```
CBIT/
├── .gitignore                 ← Excludes .env files
├── backend/
│   ├── .env                   ← Local secrets (NOT pushed to git)
│   ├── .env.example           ← Template for env vars
│   ├── build.sh               ← Render build script
│   ├── render.yaml            ← Render service config
│   ├── requirements.txt       ← Python dependencies
│   ├── main.py                ← FastAPI entry point
│   └── app/                   ← Application code
└── frontend/
    ├── .env.example            ← Template for env vars
    ├── vercel.json             ← Vercel config (SPA routing + cache headers)
    ├── package.json            ← Node dependencies
    ├── vite.config.js          ← Build optimizations
    ├── index.html              ← Entry HTML (optimized paint)
    └── src/                    ← React application code
```
