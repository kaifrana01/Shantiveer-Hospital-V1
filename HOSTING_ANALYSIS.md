# ShantiVeer HMS — Hosting Platform Analysis
### Why the App Feels Slow on Vercel, and What to Do About It

*Prepared for internal review — July 2026*

---

## The Problem We Kept Running Into

After deploying ShantiVeer HMS on Vercel, the most consistent complaint was that
pages sometimes take 3–5 seconds to load — especially first thing in the morning
or after a lunch break. Staff would click the login button and just... wait.

We dug into it. The issue is not the code. The code is well-optimised. The issue
is a fundamental mismatch between what Vercel is designed for and what a hospital
management system actually needs.

---

## Why Vercel Is Slow for This App

### 1. Serverless Architecture — The Cold Start Problem

Vercel runs your app as serverless Lambda functions. This means your Django
application is not running continuously in the background. Instead, it starts up
fresh for each request (or group of requests) and then shuts down after a period
of inactivity.

When a request arrives and no warm instance is available, Vercel has to:
- Spin up a new Python environment
- Load Django and all its apps (we have 14 URL modules)
- Import all models, middleware, and dependencies
- Then finally handle the actual request

This "cold start" adds 2–5 seconds of delay. For a hospital receptionist
registering a patient at 8:30am, this is noticeable and frustrating.

The problem gets worse because Django is a heavy framework. It imports a lot on
startup — our app alone has OPD, IPD, Lab, Pharmacy, Ultrasound, Prescription,
UHID, MasterData, Income, Expenses, History, and Accounts. Every cold start
loads all of it.

### 2. No Persistent Database Connections

On a normal server, Django keeps a pool of open database connections. When a
request comes in, it grabs one from the pool and runs the query immediately.

On Vercel, every Lambda invocation is a new process. There is no connection pool.
Every single request has to open a fresh TCP connection to the Aiven MySQL
database in Europe, complete the SSL handshake, authenticate, and then run the
query. This adds 50–100ms to every database operation just from connection
overhead.

We set `CONN_MAX_AGE=0` specifically because of this — persistent connections
would break on serverless, not help it.

### 3. In-Process Cache Is Useless

Django's default cache backend (LocMemCache) stores data in Python's memory.
On a normal server with one running process, this works fine. On Vercel, each
Lambda instance has its own separate memory. There could be 5 or 10 Lambda
instances running simultaneously to handle concurrent requests, and they share
nothing.

This means:
- Login brute-force counters reset between requests (security risk)
- Dashboard chart cache misses every time
- RBAC role lookups hit the database on every request

We worked around this by using the database as a cache backend, which works
but is not as fast as a proper in-memory cache.

### 4. Vercel Is Built for Frontend, Not Django

Vercel was designed for Next.js and static site generation. Django is a
backend framework that expects to run as a long-lived process. Vercel does
support Python, but it's a second-class citizen — the tooling, the docs,
the optimisations are all built around JavaScript frameworks.

The `maxLambdaSize` limit (we had to raise it from 15MB to 50MB), the
routing configuration, the inability to run Gunicorn with multiple workers —
all of these are symptoms of trying to fit a square peg into a round hole.

### 5. Session Handling Overhead

`SESSION_SAVE_EVERY_REQUEST` was enabled, which wrote a database row on
every single page load — including read-only pages like the patient list.
With 200 patients being processed each day across 10+ staff members, that
was thousands of unnecessary database writes per day.

We disabled this, but it's a good example of how Vercel's stateless nature
forces workarounds that add up.

---

## What We Fixed While Still on Vercel

Even though Vercel has fundamental limitations for this app, we made
significant improvements that are worth documenting:

| What was fixed | Impact |
|---|---|
| `WHITENOISE_AUTOREFRESH = False` in production | Stopped per-request file system scans |
| `CompressedManifestStaticFilesStorage` | CSS/JS cached by browsers for 1 year |
| `SESSION_SAVE_EVERY_REQUEST = False` | Eliminated ~thousands of unnecessary DB writes/day |
| RBAC role cached in session | Eliminated 1 DB query per authenticated request |
| `get_user_role()` reduced from 2 DB queries to 1 | Halved group lookup cost |
| `vercel.json` lambda size raised to 50MB | Stopped silent bundle truncation |
| History page default 7-day window | Eliminated full-table scans on page load |
| History diffs computed only on paginated page | Eliminated N+1 query problem (100s of queries → 30) |
| Cache fault-tolerant (try/except) | Site no longer crashes when cache table missing |
| Database cache backend on Vercel | Login protection and chart caching now work across Lambda instances |
| Cloudinary integration | Uploaded files no longer lost on cold start |
| `connect_timeout: 10` on MySQL | Cold-start DB timeouts fail in 10s instead of hanging for 30s |
| IPD document upload fixed for edit mode | Documents now save correctly when editing existing admissions |

These changes make Vercel workable. But the cold start problem remains.

---

## Platform Comparison

We evaluated four platforms specifically for ShantiVeer HMS running at
200 patients per day with 10 staff users.

### What 200 patients/day actually means in server terms

- Each patient generates roughly 15–20 page requests across registration,
  OPD, lab, billing, and discharge
- Add staff browsing, dashboard refreshes, and API calls
- Total: approximately 3,000–4,000 HTTP requests per day
- Peak load: 8am–12pm morning rush — roughly 2–3 requests/second
- RAM requirement: ~300–500 MB for Django + Gunicorn with 2–3 workers
- CPU: Low to moderate — most work is DB queries, not computation

---

### Vercel

Vercel is the platform we're currently on.

**The good:** It's free on the Hobby plan, deployment is dead simple (push
to GitHub and it's live), SSL and CDN are automatic, and the static file
serving is fast.

**The bad:** The Hobby plan is for personal projects. Commercial use requires
the Pro plan at $20/month. Beyond the cost, the serverless architecture
means cold starts are always present. You cannot run Gunicorn with persistent
workers. The cache situation requires workarounds. File uploads go to `/tmp`
and are lost unless you use an external service like Cloudinary.

**Cold starts:** Yes, 2–5 seconds after any period of inactivity.

**Monthly cost for the hospital:** $0 on Hobby (but technically violates
ToS for commercial use). $20/month on Pro (~₹1,700). For $20/month you still
have all the architectural limitations — you're just paying to use it
commercially.

**Verdict:** Fine for getting started. Not the right long-term home for
a production hospital system.

---

### Railway ⭐ Recommended

Railway is a container-based platform that runs your app as a persistent
process — exactly how Django is meant to run.

Your existing `Procfile` works without changes:
```
web: gunicorn ShantiVeer_hms.wsgi:application --workers 3 --bind 0.0.0.0:$PORT
```

Your existing `build.sh` works without changes. Your environment variables
copy over directly. Migration from Vercel takes about 20 minutes.

**Architecture:** Persistent container. No cold starts. Your app stays
running 24/7. Gunicorn manages a pool of workers. Database connections
are persistent. The cache actually works as intended.

**Cold starts:** None (unless you explicitly enable sleep mode, which you
wouldn't for a hospital app).

**Resource usage estimate for this app:**

Railway bills per actual resource consumed:
- RAM: ~512MB average × 24h × 30 days = ~$1.85/month
- vCPU: ~0.3 vCPU average × $20/vCPU/month = ~$0.90/month
- Total actual usage: ~$2.75/month

The Hobby plan costs $5/month, and this acts as a minimum commitment — the
$2.75 usage is covered within the $5 subscription. You only pay more if
your actual resource usage exceeds $5, which won't happen at 200 patients/day.

**Monthly cost for the hospital:**

| Service | Cost |
|---|---|
| Railway Hobby plan | $5/month (~₹420) |
| Aiven MySQL (free tier) | ₹0 |
| Cloudinary (free 25GB tier) | ₹0 |
| **Total** | **~₹420/month** |

**What you gain by moving to Railway:**
- Staff log in instantly every morning, no waiting
- Real Gunicorn workers with proper concurrency
- Persistent DB connections — faster queries
- LocMemCache works properly (single process, shared memory)
- No need for database cache workarounds
- No commercial use restrictions

**Verdict:** Best fit for this app. The $5/month cost is negligible for a
running hospital.

---

### Render

Render is probably the most well-known alternative to Heroku. It's polished,
the documentation is good, and Django deployment is straightforward.

**Architecture:** Persistent container on paid plans. On the free tier,
services sleep after 15 minutes of inactivity and take 30–60 seconds to
wake up. For a hospital app, the free tier is simply not usable — a
60-second wait when the first patient arrives in the morning is not
acceptable.

**Cold starts:** On free tier — yes, 30–60 seconds after 15 minutes idle.
On paid Starter instance — none.

**Monthly cost for the hospital:**

| Service | Cost |
|---|---|
| Render Starter instance (512MB RAM) | $7/month (~₹590) |
| Aiven MySQL | ₹0 |
| Cloudinary | ₹0 |
| **Total** | **~₹590/month** |

One thing to note: as of April 2026, Render's free plan dropped included
bandwidth from 100GB to 5GB/month. For a hospital app where staff are
downloading PDF reports and lab results daily, 5GB goes quickly.

**Verdict:** Good platform, slightly more expensive than Railway for the
same specs. The free tier is not viable for production use.

---

### Koyeb

Koyeb is less well-known but genuinely interesting. They run on bare metal
(not AWS or GCP), which keeps their costs down and lets them offer a free
tier with persistent instances.

**Architecture:** Container-based. Currently persistent on the free tier,
though they have announced scale-to-zero as an upcoming feature for free
instances, which would introduce cold starts.

**Cold starts:** Currently none on free tier. May change when scale-to-zero
launches.

**Monthly cost for the hospital:**

| Tier | Cost |
|---|---|
| Free instance (512MB RAM, 0.1 vCPU) | ₹0 |
| Eco instance (better specs) | ~$1.61/month (~₹135) |

**The concern:** Koyeb is a smaller platform. The community is smaller, the
Stack Overflow answers are fewer, and when something breaks at 9am on a
Monday with patients waiting, you want to be on a platform with solid
documentation and a track record. For a hospital system, platform maturity
matters.

**Verdict:** Worth watching, especially if budget is a hard constraint.
Not the first choice for a production hospital system today.

---

## Summary Comparison

| | Vercel (Free) | Vercel (Pro) | Railway Hobby | Render Starter | Koyeb Free |
|---|---|---|---|---|---|
| Monthly cost | ₹0* | ₹1,700 | **₹420** | ₹590 | ₹0 |
| Cold starts | Yes (2–5s) | Yes (2–5s) | None | None | None (for now) |
| Commercial use | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| Persistent connections | ❌ No | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| Gunicorn workers | ❌ No | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| Code changes needed | — | — | None | None | Minor |
| Platform maturity | ✅ High | ✅ High | ✅ High | ✅ High | ⚠️ Medium |

*Free Hobby plan is for personal projects only — commercial use violates Vercel ToS.

---

## Our Recommendation

**Short term (now):** Stay on Vercel with all the optimisations applied.
The app is significantly faster than it was. Cold starts are still present
but the improvements to session handling, caching, and query counts have
made a real difference.

**Medium term (when ready to pay ₹420/month):** Move to Railway. It is
the right platform for this kind of app. The migration is straightforward,
the code requires no changes, and the improvement in day-to-day
responsiveness for staff will be immediately noticeable — especially
that first login of the morning.

For a hospital processing 200 patients per day, ₹420/month is the cost
of one OPD consultation. It's worth it.

---

*Document prepared based on research conducted July 2026.*
*Pricing figures sourced from official platform documentation and verified
against current published rates.*
