# 07 — Deployment Strategy

Objective: a real, reliable product on the internet for **≈$10/month at launch**, with a
scaling path that never requires a re-architecture — only bigger/more instances. Cheap is a
strategy (see [00-product-vision.md](./00-product-vision.md)), not an accident.

## Topology

```
users ──▶ Cloudflare Pages (web/ static build, global CDN, $0)
              │  HTTPS calls to api.<domain>
              ▼
          Render free tier — agent container (FastAPI, $0; UptimeRobot pings /health
          every 5 min as keep-alive so it never idle-sleeps)
              │
              ▼
          Supabase — Postgres + pgvector + Auth (free tier → $25 Pro when limits hit)
              │
              ▼
          OpenRouter / Anthropic — LLM APIs (usage-based, capped in-app)
```

Three vendors, all with meaningful free tiers, none load-bearing enough to be unmovable:
the frontend is a static bundle (any CDN), the backend is a plain Docker container (any
container host), the DB is standard Postgres (any managed PG).

## Environments

| Env | Web | Agent | DB | Purpose |
|---|---|---|---|---|
| **dev** | `npm run dev` (localhost:5173 — note: bind is IPv6 `localhost`, not 127.0.0.1) | `uvicorn --reload` :8000 | SQLite (`canvo.db`, disposable) | Daily work; fully offline capable |
| **local-prod** | built bundle | `docker compose up` | compose Postgres | Prod-parity smoke before deploy |
| **prod** | CF Pages | Render container | Supabase Postgres | The product |

A separate staging env is deliberately skipped until there are paying users; local-prod +
CI gates + instant rollback cover the risk at this scale.

## Backend host: Render free tier at launch (user decision 2026-08-17), paid when traffic arrives

| | Render free (launch) | Railway Hobby / Render Starter (upgrade) |
|---|---|---|
| Price | **$0** (750 instance-hrs/mo covers one 24/7 service) | $5 / $7 per month |
| Resources | 512MB RAM, 0.1 CPU — enough for FastAPI+SSE; Pillow renders run slower | more CPU/RAM, no sleep |
| Sleep | idles after 15 min → mitigated by **UptimeRobot pinging `/health` every 5 min** | never sleeps |
| Cold starts | still happen after each deploy and platform restarts (~30–60s) — keep-alive only prevents *idle* sleep | rare |
| Deploy | connect GitHub repo → auto-deploy on push; detects `agent/Dockerfile` | same |

**Launch posture: Render free + keep-alive ping.** The keep-alive is a widely used but
unofficial pattern — accept that Render may restart free instances at any time, and treat the
occasional cold start as a known launch-phase wart. **Upgrade trigger** (move to Railway $5 or
Render Starter $7 — the container is host-agnostic, an afternoon's work): first real users
complaining about latency, or keep-alive flakiness showing in UptimeRobot.

**DB stays on Supabase** — its free tier bundles Postgres + pgvector + Auth (three needs, $0),
and it keeps the DB decoupled from whichever compute host we're on this month.

## Deploy pipeline

1. **CI on every push to `main`** (GitHub Actions): ruff → mypy → pytest; tsc → lint → vite build.
   *(Blocker to clear first: the `anuragchaubey1224` gh token lacks `workflow` scope —
   `gh auth refresh -h github.com -s workflow`, then move `.github/ci.yml.pending` to
   `.github/workflows/ci.yml`.)*
2. **Deploy on green main**: Render auto-deploys the agent on push (enable "wait for CI
   checks to pass" in the service settings); CF Pages auto-builds `web/` on push.
3. **Migrations** (from P3): Alembic `upgrade head` as a release step before the new
   container takes traffic. Additive-first migration style (expand → migrate → contract) so
   old/new code can overlap during deploys.
4. **Rollback**: redeploy the previous commit from the Render dashboard (or `git revert` +
   push); DB migrations must always be reversible one step (`downgrade -1` tested in CI).

## Configuration & secrets

- All config via env vars, documented in `agent/.env.example` — `LLM_MODEL`,
  `OPENROUTER_API_KEY`/`ANTHROPIC_API_KEY`, `DATABASE_URL`, plus (P3) Supabase JWT settings
  and quota knobs.
- Prod secrets live in the platform's secret store (Render service → Environment), never in the repo,
  never in build args, never printed in logs.
- CORS locked to the web origin(s) in prod; permissive only in dev.

## Cost controls (day-one requirements, not afterthoughts)

These protect the token bill *before* any auth exists (P0 exit criteria):

1. **Per-IP daily AI-generation cap** (deterministic paths uncapped — they're free for us).
2. **Payload size caps** on `/agent/stream` (a pasted 5MB "PRD" is a bug or an attack).
3. **Hard per-run cost ceiling** in guardrails (max LLM calls per run — planner + bounded
   critic loop already bounds this structurally; enforce it explicitly anyway).
4. **Spend alarms**: OpenRouter/Anthropic dashboard limits + a daily spend check; kill-switch
   env var (`AI_DISABLED=1`) that degrades the product to deterministic-only mode instead of
   taking it down.
5. **Model allowlist** (ADR-009): nobody — including us at 2am — points prod at an
   unverified model without running the evals.

## Monitoring & operations

| Concern | Tool | Cost |
|---|---|---|
| Uptime **+ keep-alive** | UptimeRobot on `/health`, 5-min interval (double duty: alerting *and* preventing Render free-tier idle sleep) | $0 |
| Errors | Sentry (agent + web), from P3 | $0 tier |
| Logs | platform logs (Render dashboard) | $0 |
| Agent behavior | our own per-node tracing + `generations` metering table (v1/P3) | $0 |
| Backups | Supabase automated backups; weekly `pg_dump` to object storage once there are real users | ~$0 |

## Scaling path (in order, only when a step is actually needed)

1. **Render free instance + keep-alive** — SSE is I/O-bound; async FastAPI comfortably holds
   many concurrent streams even at 0.1 CPU. This is the launch posture.
2. **Paid instance** (Railway $5 / Render Starter $7) — the moment real users feel cold starts
   or the 0.1 CPU hurts vision renders.
3. **Vertical bump** (more RAM/CPU) — Pillow rendering and YAML parsing are the only CPU spots.
4. **Horizontal replicas** — the service is stateless (state in Postgres); no sticky sessions
   needed since a stream lives within one request.
4. **Split the vision-render path** into a small worker queue *only if* render CPU measurably
   hurts stream latency.
5. **Postgres**: Supabase Pro → bigger instance. pgvector at our scale (thousands of patterns,
   not millions) never needs a dedicated vector DB.

What we deliberately do **not** build now: Kubernetes, Terraform, multi-region, Redis,
service mesh, staging clusters. Each is an answer to a problem we don't have; the docs-first
rule is to write down the trigger condition instead (see table above) and move on.

## Database migrations

Alembic owns the schema; nothing else is allowed to change it. `create_all` was fine while
there was nothing to preserve, but it silently skips tables that already exist — so a new
column on an existing install simply never appeared.

```bash
cd agent
alembic revision --autogenerate -m "what changed"   # after editing app/db/models.py
alembic upgrade head                                 # apply
alembic downgrade -1                                 # step back
alembic upgrade head --sql                           # review the SQL without running it
```

The URL always comes from `DATABASE_URL`, never from `alembic.ini`, so a stale config file
can't point a migration at the wrong database.

**On startup** the app runs `upgrade head` itself, which is right for the single instance we
deploy. For more than one, set `RUN_MIGRATIONS=false` and run the upgrade once as a release
step — otherwise two booting workers race for the migration lock.

**Databases created before Alembic** (by the old `create_all`) have every table but no
version row. Startup detects that and *stamps* them at head instead of trying to create
what already exists, so an existing install keeps its data.

`tests/test_migrations.py` asserts that after running the migrations, Alembic sees nothing
left to autogenerate. That is what catches the classic mistake: a column added to a model,
conjured locally by an old `create_all`, with no migration written for production.
