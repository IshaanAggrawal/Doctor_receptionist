# DentaQ Deployment Guide

This document outlines the infrastructure required to run DentaQ, how to deploy it for free when showing it to a client, and how to scale it for real-world production.

---

## 1. Core Infrastructure Required

No matter where you deploy, the system requires **four external services** to function:

1. **PostgreSQL Database**: To store clinics, slots, and appointments.
2. **Redis Cache**: To handle rate-limiting, fast slot reading, and OTP generation.
3. **Twilio Account**: To send the SMS OTPs and 3-Tier waiting room notifications.
4. **Telegram Bot Token**: (Optional) If using the bot, acquired via `@BotFather` on Telegram.

---

## 2. Option A: Demoing to a Client (Free Tier)

When you are pitching this software to a clinic or showing it off in an interview, you don't want to spend money on servers. You can host this entire stack for **$0/month**.

### The Setup:
* **Database (PostgreSQL)**: **[Supabase](https://supabase.com/)** (Free Tier)
  - Gives you a generous free Postgres database. 
  - Provides the `SUPABASE_URL` and `SUPABASE_ANON_KEY` for the REST API.
* **Cache (Redis)**: **[Upstash](https://upstash.com/)** (Free Tier)
  - Provides a free, serverless Redis database.
  - Gives you the `REDIS_URL`.
* **The Web Portal (`app.py`)**: **[Streamlit Community Cloud](https://share.streamlit.io/)** (Free)
  - Connect your GitHub repository.
  - Streamlit will host the app for free.
  - *Alternative: [Render.com](https://render.com/) Web Service (Free Tier).*
* **The Telegram Bot (`bot.py`)**: **[Render.com](https://render.com/)** (Free Tier)
  - Deploy as a "Background Worker" so it runs continuously.
* **The No-Show Cron Job**: **[cron-job.org](https://cron-job.org/)** (Free)
  - You can expose the cron script via a secure API endpoint in your app, and have cron-job.org ping it every 5 minutes for free.

---

## 3. Option B: Production (Real-World Usage)

When a clinic actually buys your software, you need it to be 100% reliable, fast, and under a custom domain (e.g., `booking.drahmedclinic.com`). The free tiers will "sleep" if unused, which is unacceptable for a real business.

### The Setup (Estimated ~$20-30/month):
* **Database**: **Supabase Pro** ($25/mo) or **AWS RDS** 
  - Ensures automated daily backups, no sleep-states, and high connection pooling.
* **Cache**: **Upstash** (Pay-as-you-go) or **AWS ElastiCache**
  - Handles thousands of concurrent slot reads without breaking a sweat.
* **The Web Portal (`app.py`)**: **[Railway.app](https://railway.app/)** or **[Render.com](https://render.com/)** ($5-$7/mo)
  - Excellent platform-as-a-service (PaaS). You just push your code to GitHub, and it automatically builds and deploys it.
  - They provide easy custom domain linking with auto-renewing SSL certificates.
* **The Telegram Bot & Cron Job**: **Railway.app** ($5/mo)
  - You can spin up the bot as a background worker on the same Railway project.
  - Railway has built-in Cron Job support to run `cron/no_show_cleanup.py` every 5 minutes flawlessly.
* **DNS & Security**: **[Cloudflare](https://www.cloudflare.com/)**
  - Point the clinic's domain name to Cloudflare to protect the portal from DDoS attacks.

---

## 4. Quick-Start Deployment Steps (For Railway/Render)

1. **Push to GitHub**: Commit this entire codebase to a private GitHub repository.
2. **Create the DB**: Go to Supabase, create a project, and run `src/database/schema.sql` in their SQL Editor.
3. **Create the Cache**: Go to Upstash, create a Redis DB, and copy the URL.
4. **Deploy**: 
   - Go to Railway or Render.
   - Click "New Project" -> "Deploy from GitHub repo".
   - Select your DentaQ repository.
5. **Environment Variables**:
   - In the deployment dashboard, paste all the variables from your `.env.example` (DB URL, Redis URL, Twilio keys, etc.).
6. **Launch**: The platform will install `requirements.txt` and run `streamlit run app.py`. Your Smart Clinic is now live on the internet!
