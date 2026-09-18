# Deploy runbook

Both paths use free tiers and take about ten minutes. You need a GitHub repo with this
code pushed to it.

---

## Option A — Render (recommended: one blueprint, includes Postgres)

1. Push this repo to GitHub.
2. Render dashboard → **New** → **Blueprint** → pick the repo. Render reads
   `render.yaml` and proposes three services: `alpago-db`, `alpago-api`, `alpago-web`.
3. It will prompt for `AI_API_KEY` (marked `sync: false`). Paste a Groq key, or leave it
   blank — the app runs fine without one and shows deterministic explanations instead.
4. **Apply**. First deploy takes ~5 minutes; the API runs migrations and, because
   `SEED_ON_STARTUP=true`, loads the sample workbook data on boot.
5. Once `alpago-api` is live, copy its URL (e.g. `https://alpago-api.onrender.com`).
   If it differs from that default, edit the rewrite rule in `render.yaml`:

   ```yaml
   - type: rewrite
     source: /api/*
     destination: https://<your-api-host>/api/*
   ```

   Commit and push; `alpago-web` redeploys.
6. Open the `alpago-web` URL. That is the public link to share.

**Free-tier caveat worth knowing before a demo:** Render free web services sleep after
15 minutes idle and take ~50 seconds to wake. Load the URL a minute before showing it.
Free Postgres instances also expire after 90 days.

---

## Option B — Railway

1. `railway init` in the repo, or create a project from the GitHub repo in the dashboard.
2. Add a **PostgreSQL** plugin. Railway injects `DATABASE_URL` automatically — but as
   `postgresql://`, which SQLAlchemy 2 needs as `postgresql+psycopg2://`. Set an
   explicit variable on the API service:

   ```
   DATABASE_URL=postgresql+psycopg2://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
   ```

3. Set `SEED_ON_STARTUP=true` and, optionally, `AI_API_KEY`.
4. The API service uses `railway.json` (builds `backend/Dockerfile`, runs `./start.sh`).
   Generate a public domain for it.
5. For the frontend, add a second service from `frontend/`, build command
   `npm ci && npm run build`, and set `VITE_API_BASE_URL` to
   `https://<api-domain>/api/v1`. Then set `CORS_ORIGINS` on the API to the web
   service's origin (not `*`).

---

## Smoke test after deploying

```bash
API=https://<your-api-host>

curl -s $API/health
curl -s $API/api/v1/dashboard
# expect: projects 7, employees_active 56

PRJ=$(curl -s $API/api/v1/projects | python3 -c \
  "import sys,json;print([p['id'] for p in json.load(sys.stdin) if p['project_code']=='PRJ007'][0])")

curl -s -X POST $API/api/v1/projects/$PRJ/allocate | python3 -m json.tool | head -20
# expect: total_man_days 74, actual_working_days 52, shortages 0

curl -s $API/api/v1/conflicts        # expect: []
```

Then in the browser: open PRJ007, confirm the Gantt runs 01-Sep-2026 → 31-Oct-2026,
press **Generate AI Insights**, and check the Conflicts page is empty.

---

## Security notes before this touches anything real

The assessment build has no auth by design. Three things to fix before it sees
production data:

- **`CORS_ORIGINS=*`** ships as the default so the demo works from anywhere. Set it to
  the exact web origin in production.
- **No authentication or authorisation.** Every endpoint is open, including the
  destructive ones (`DELETE /employees/{id}`, `DELETE /projects/{id}`). Employee names,
  joining dates and designations are personal data.
- **`AI_API_KEY` must only ever be an environment variable.** It is referenced with
  `sync: false` in `render.yaml` precisely so it never lands in the repo. Note that
  allocation facts — employee names, codes and dates — are sent to the LLM provider
  when insights are generated; if that is a problem for the client's data policy, leave
  `AI_ENABLED=false` and the deterministic explanations cover the same ground.
