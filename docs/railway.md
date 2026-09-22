# Nova Demo on Railway Free

For all services and all 19 scenarios, use the
[Railway Hobby guide with a $15 budget](railway-hobby.md).

This deployment runs one Django service with SQLite on a persistent volume.
It includes both interface languages and the FastAPI/GraphQL demo dependencies.
Redis and Memcached are not provisioned: their three scenarios explicitly report
`skipped` until those services are connected. This is a small interactive demo,
not the PostgreSQL + Redis + Memcached integration environment used in CI.

## Free plan and usage

Checked on 2026-09-22: [Railway Free](https://railway.com/pricing) includes
$1 of monthly resource usage, up to 0.5 GB RAM per service, one project,
three services and one 0.5 GB volume. An eligible trial has separate temporary
credits. Free does **not** promise an always-on application at no cost.

Keep the workspace on Free, enable **Serverless**, and monitor Usage/Billing.
Do not upgrade to Hobby or add paid resources for this deployment.
Serverless can sleep an inactive service and wake it on a request; wake-up adds
latency. A busy service may never sleep, and persistent storage also uses credits.
Keep copies of any demo data you need: a volume is not a backup.

## Deploy from GitHub

1. Merge the deployment PR after the **Demo checks** workflow is green. Keep the
   existing `demo (sqlite)` and `demo (postgres)` required checks.
2. In Railway select your Free workspace, then **New Project → Deploy from GitHub
   repo → Artem7898/nova-demo**. Select `main`, root directory `/`.
   If an initial deploy starts before variables and volume are ready, it is
   expected to fail safely. Configure the service and redeploy.
3. Attach one **Volume** to the web service, mount path **`/data`**. Railway supplies
   `RAILWAY_VOLUME_MOUNT_PATH` automatically. Do not mount it over `/app`.
4. In **Variables**, add a private `DJANGO_SECRET_KEY`. Generate it locally:

   ```bash
   uv run --locked python -c 'import secrets; print(secrets.token_urlsafe(64))'
   ```

   Paste the value directly into Railway. Do not commit it or send it in chat.
   Keep it unchanged on future deploys so visitor sessions remain valid.
   `NOVA_DEMO_DB=sqlite` is optional and is the default for this profile.
   Do not set Redis/Memcached URLs until real services exist.
5. Railway detects the root **Dockerfile**. Leave custom build, start and
   pre-deploy commands empty: the image starts itself. Set **Healthcheck Path**
   to **`/healthz/`**, with a 120-second timeout. Keep **one replica**.
   Enable **Serverless** before deploying these changes.
6. In **Networking → Public Networking → Generate Domain**, create a Railway
   domain pointing at port **8000**. Set `PORT=8000` if Railway has not already
   supplied it. The launcher binds `0.0.0.0:$PORT`.
   `RAILWAY_PUBLIC_DOMAIN` is used for allowed hosts and trusted HTTPS origins.
   Redeploy after generating or changing the domain.
7. Deploy, wait for the healthcheck, and open the generated **HTTPS** URL.
   Check `/`, `/catalog/`, RU/EN, and **Run all checks**. Without remote caches,
   expect 16 successful scenarios and 3 explicit skips, not 19 remote-service checks.
8. Restart the service and verify that the same browser still sees its catalog.
   SQLite and media live under the attached volume; collected static assets live
   in the image. No admin account is created automatically.

The profile rejects startup without a private secret or, on Railway, an attached
volume. Database migrations run **at startup**, after the volume is mounted.
Railway does not mount volumes during builds or pre-deploy commands.

`config.railway_settings` trusts the Railway HTTPS proxy and redirects other
requests to HTTPS. `/healthz/` accepts Railway's internal HTTP healthcheck host;
it checks the database without creating a session or a visitor sandbox. It does
not require optional cache services to be present.

## Updates and housekeeping

Use a feature branch and PR for each update. In Railway's GitHub deployment
settings, enable **Wait for CI** if available, and keep deployment tracking `main`.
The single replica/volume setup can have a short interruption during redeployment.

The demo uses one synchronous Gunicorn worker: some lab scenarios temporarily
change process-local state. Do not increase workers/threads to simulate production
capacity. Use the separate test suite for concurrency guarantees.

Visitor data accumulates on the small volume. Periodically run these commands in
the service environment (for example with Railway SSH):

```bash
python manage.py prune_demo --days 7
python manage.py clearsessions
```

The first command intentionally deletes demo workspaces older than seven days.
Take a database/media backup before cleanup or schema changes. Uploaded images
are preserved on the volume and served only to their visitor workspace or staff;
the demo catalog's bundled SVG images are served publicly by WhiteNoise.

## Local production smoke test

```bash
uv run --locked pytest -q tests/test_deployment.py
docker build -t nova-demo:railway .
```

The tests run the actual startup script and Gunicorn with a temporary database,
check HTTP/HTTPS behavior, hashed static assets, secure cookies, both languages,
and verify database contents across a process restart. CI additionally builds and
runs the Docker image. The image contains no `.env`, local SQLite database, or
development dependencies.

Reference: [volumes](https://docs.railway.com/volumes),
[healthchecks](https://docs.railway.com/deployments/healthchecks),
[Serverless](https://docs.railway.com/deployments/serverless).
