# 🚀 EventLens AI — Complete Cloud Deployment Guide

This guide walks you through deploying **EventLens AI** to production with high availability, fast AI vector face-matching, and zero-downtime scalability.

---

## 📑 Architecture Overview

```mermaid
graph LR
    User["Attendee / Admin Device"] -->|Web Browser| Vercel["Vercel Frontend (Next.js 16)"]
    Vercel -->|Proxy /api & /static| Backend["Render / Railway (FastAPI + PyTorch)"]
    Backend -->|Vector & DB Queries| Supabase["Supabase (PostgreSQL + pgvector)"]
    Backend -->|Photo Storage| Storage["Supabase Storage / CDN"]
```

- **Frontend**: [Vercel](https://vercel.com) (Global Edge CDN, Automatic SSL, Next.js Serverless)
- **Backend**: [Render](https://render.com) or [Railway](https://railway.app) (Python 3.10, PyTorch, FaceNet)
- **Database & Storage (Optional / Recommended)**: [Supabase](https://supabase.com) (PostgreSQL, `pgvector`, Object Storage)

---

## 🛠️ Step 1: Deploy Backend to Render (Free / Starter)

### Option A: 1-Click Render Blueprint (Recommended)
1. Go to [dashboard.render.com](https://dashboard.render.com/) and click **New +** -> **Blueprint**.
2. Connect your GitHub repository: `https://github.com/Santhosh-555-i/my-website.git`.
3. Render will automatically detect [`render.yaml`](file:///c:/Users/Santhosh/Downloads/stitch_hello_world_project%20%281%29/render.yaml).
4. Click **Apply**. Render will automatically provision the FastAPI service, install CPU-optimized PyTorch, and launch the server.

---

### Option B: Manual Web Service on Render
1. Go to [dashboard.render.com](https://dashboard.render.com/) and click **New +** -> **Web Service**.
2. Select your repository `Santhosh-555-i/my-website`.
3. Fill in the service configuration:
   - **Name**: `eventlens-backend`
   - **Region**: Select closest to your users (e.g., *Oregon (US West)* or *Frankfurt (EU)*)
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install --no-cache-dir -U pip && pip install --no-cache-dir -r requirements-cpu.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
     ```
4. Under **Environment Variables**, add:
   - `PYTHON_VERSION` = `3.10.13`
   - `SIMILARITY_THRESHOLD` = `0.68`
   - `ADMIN_EMAIL` = `santosh2005th@gmail.com`
   - `ADMIN_PASSWORD` = `admin123` *(or choose your custom secure passcode)*
   - `CORS_ORIGINS` = `*`
   - *(Optional for Supabase)*: `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`
5. Click **Create Web Service**.
6. Once deployed, note your backend URL:  
   👉 `https://eventlens-backend-xxxx.onrender.com`

---

## 🚂 Alternative Step 1: Deploy Backend to Railway

1. Go to [railway.app](https://railway.app) and click **New Project** -> **Deploy from GitHub repo**.
2. Select `Santhosh-555-i/my-website`.
3. In service settings, set **Root Directory** to `/backend` (or leave default to let Railway use [`backend/Dockerfile`](file:///c:/Users/Santhosh/Downloads/stitch_hello_world_project%20%281%29/backend/Dockerfile)).
4. Under **Variables**, add:
   - `PORT` = `8000`
   - `SIMILARITY_THRESHOLD` = `0.68`
   - `ADMIN_EMAIL` = `santosh2005th@gmail.com`
   - `ADMIN_PASSWORD` = `admin123`
5. Go to **Settings** -> **Networking** -> click **Generate Domain** to get your public backend URL (e.g. `https://photo-production-xxxx.up.railway.app`).

---

## 🌐 Step 2: Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) and click **Add New...** -> **Project**.
2. Import your GitHub repository (`Santhosh-555-i/my-website`).
3. In the project setup screen:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: Click *Edit* and select **`frontend`**.
4. Expand the **Environment Variables** section and add:
   | Key | Value | Description |
   |---|---|---|
   | `BACKEND_INTERNAL_URL` | `https://your-backend.onrender.com` | Your Render/Railway backend URL |
   | `NEXT_PUBLIC_BACKEND_URL` | `https://your-backend.onrender.com` | Public backend fallback URL |
   | `NEXT_PUBLIC_API_URL` | `/api` | Relative proxy URL |
5. Click **Deploy**.
6. In ~60 seconds, Vercel will give you your live URL (e.g., `https://eventlens-ai.vercel.app`)! 🎉

---

## 🗄️ Step 3 (Optional): Supabase Cloud Database & Storage Setup

If you want cloud-hosted PostgreSQL with pgvector and CDN photo storage instead of local SQLite:

1. Create a free project at [supabase.com](https://supabase.com).
2. Go to **SQL Editor** in Supabase, copy the contents of [`backend/schema.sql`](file:///c:/Users/Santhosh/Downloads/stitch_hello_world_project%20%281%29/backend/schema.sql), paste and click **Run**.
3. Go to **Storage** -> confirm the **`photos`** bucket is created (and set to *Public*).
4. Go to **Project Settings** -> **API**:
   - Copy **Project URL** (`https://xyz.supabase.co`)
   - Copy **anon / service_role API Key**
5. Go to **Project Settings** -> **Database**:
   - Copy **Connection string (URI)**
6. In Render or Railway, add these 3 variables to your backend:
   - `SUPABASE_URL` = `https://xyz.supabase.co`
   - `SUPABASE_KEY` = `<your-supabase-key>`
   - `DATABASE_URL` = `postgresql://postgres:password@db.xyz.supabase.co:5432/postgres`

---

## 🐳 Step 4: Self-Hosted Docker Compose on VPS (AWS / DigitalOcean / Hetzner)

If you have a Linux server/VPS:

1. Clone repository on your server:
   ```bash
   git clone https://github.com/Santhosh-555-i/my-website.git
   cd photo
   ```
2. Run the stack with Docker Compose:
   ```bash
   docker compose up -d --build
   ```
3. EventLens AI is live:
   - Frontend: `http://<your-server-ip>:3000`
   - Backend API: `http://<your-server-ip>:8000/docs`

---

## 🧪 Step 5: Post-Deployment Verification Checklist

- [ ] **Health Check**: Visit `https://your-backend.onrender.com/api/health` -> verify status is `"healthy"`.
- [ ] **Frontend**: Open your Vercel URL -> verify homepage loads with live animations and UI.
- [ ] **Admin Login**: Go to `/admin` -> log in with your admin credentials.
- [ ] **Create Event**: Create an event (e.g. `TECH-CONF-2026`) and upload batch sample photos.
- [ ] **Selfie Matching**: Go to `/find-photos` or `/events/TECH-CONF-2026`, capture/upload a selfie, and verify matches return in < 1 second.
- [ ] **Temporary Sharing**: Select photos -> click "Share Selected Photos" -> test opening the generated link in an Incognito window.
