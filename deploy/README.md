# Production deployment

Production runs on a DigitalOcean Ubuntu host:

- nginx terminates TLS for `https://rwcweather.com`.
- Next.js runs under PM2 as `rwcwx-app` on port 3000.
- Flask/uWSGI runs under systemd as `rwcwx` and serves `/api/`.
- The checkout is `/home/ben/rwcweather` on `ben@138.68.56.237:8294`.

The deployment scripts do not commit or push source control changes. Commit and push separately so GitHub remains the source of truth.

## Frontend quick start

Requirements on the local machine:

- SSH access to the production host using the normal SSH agent/key.
- Node.js, npm, rsync, curl, and Python 3.
- Frontend dependencies installed in `web/app/node_modules`.
- The same Next.js version locally and on production.

From the repository root:

```sh
cd web/app
npm install --no-package-lock --legacy-peer-deps
cd ../..
./deploy/deploy_frontend.sh
```

Preview the files that would be synchronized without restarting or changing production:

```sh
./deploy/deploy_frontend.sh --dry-run
```

The script:

1. Checks SSH access and verifies that local and production Next.js versions match.
2. Builds the optimized frontend locally. For modern Node versions it enables the OpenSSL compatibility mode required by Next 11.
3. Syncs frontend source and `.next`, excluding dependencies, package manifests, and the build cache.
4. Restarts only the `rwcwx-app` PM2 process.
5. Verifies the public monthly report and the all-periods API.

Override production settings with environment variables when necessary:

| Variable | Default |
| --- | --- |
| `RWCWX_DEPLOY_HOST` | `ben@138.68.56.237` |
| `RWCWX_DEPLOY_PORT` | `8294` |
| `RWCWX_REMOTE_ROOT` | `/home/ben/rwcweather` |
| `RWCWX_PUBLIC_URL` | `https://rwcweather.com` |
| `RWCWX_FRONTEND_PROCESS` | `rwcwx-app` |

To verify production without deploying:

```sh
./deploy/verify.sh
```

## Dependency changes

The frontend server is intentionally small, so builds happen locally. When `package.json` changes:

1. Install and test the exact dependency set locally.
2. Sync `package.json` to production manually; the normal frontend script deliberately excludes package manifests.
3. Run `npm install --no-package-lock --legacy-peer-deps` in `/home/ben/rwcweather/web/app` on production.
4. Confirm `node -p 'require("next/package.json").version'` matches locally and remotely.
5. Run `./deploy/deploy_frontend.sh`.

Do not deploy a `.next` build produced by a different Next.js version than the production runtime.

## Backend deployment

Deploy backend changes from the repository root:

```sh
./deploy/deploy_backend.sh
```

Preview the files that would be synchronized without changing or restarting production:

```sh
./deploy/deploy_backend.sh --dry-run
```

If `requirements.txt` changed, review it and explicitly allow installation:

```sh
./deploy/deploy_backend.sh --install-deps
```

The backend deploy script:

1. Syntax-checks every local Python file.
2. Confirms SSH access, the production virtualenv, and whether dependencies changed.
3. Synchronizes the backend package, entrypoint, requirements, and uWSGI configuration without deleting remote files.
4. Compiles and imports the uploaded application using the production runtime and environment.
5. Gracefully reloads the `rwcwx` uWSGI master with `SIGHUP`; the service account owns that process, so deployment does not depend on interactive sudo access.
6. Verifies the health endpoint, live-dashboard response shape, and a default two-second latency ceiling.

Run the backend verification independently with:

```sh
./deploy/verify_backend.sh
```

Override the latency ceiling with `RWCWX_MAX_LIVE_SECONDS`. The host, port, remote root, public URL, service name, and remote environment file can be overridden with `RWCWX_DEPLOY_HOST`, `RWCWX_DEPLOY_PORT`, `RWCWX_REMOTE_ROOT`, `RWCWX_PUBLIC_URL`, `RWCWX_BACKEND_SERVICE`, and `RWCWX_REMOTE_ENV_FILE`.

Changes to `rwcwx/job/save_latest.py` require restarting that separate ingestion process as documented in the server runbook.

## Operations and troubleshooting

Useful production commands:

```sh
# Frontend status and logs
pm2 status rwcwx-app
pm2 logs rwcwx-app --lines 100 --nostream

# Flask status and logs
sudo systemctl status rwcwx --no-pager
journalctl -u rwcwx --since today

# nginx logs
sudo tail -n 100 /var/log/nginx/access.log
sudo tail -n 100 /var/log/nginx/error.log
```

If frontend verification fails, inspect PM2 logs, fix or revert the source locally, and rerun the frontend deployment script. The rsync step does not delete older hashed assets, so clients already loading the previous build can finish their requests during deployment.
