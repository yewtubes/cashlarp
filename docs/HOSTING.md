# Hosting and backups

## Local setup

Install Python 3.10 or newer, clone the repository and run `python3 -B run.py`.
Open http://127.0.0.1:3000/login and create your first account using the original client. Fresh databases have no users. No Python or npm packages are required at runtime.
`./start.sh` and `start.bat` use the same launcher. Options include `--host`,
`--port` and `--db`.

With Docker and the Compose plugin, `docker compose up -d --build` starts the
app on http://127.0.0.1:3000. The named `cashlarp_data` volume preserves SQLite
across image replacements. One app instance should own that volume.

## VPS with a domain

1. Install Docker Engine and the Compose plugin on your VPS.
2. Point the domain's A record to the VPS; add AAAA only if IPv6 works.
3. Allow inbound TCP ports 80 and 443. Port 3000 remains on loopback.
4. Run `python3 tools/configure_host.py your-domain.com` in the repository.
5. Read `.env` privately for the hosting username and generated password.
6. Run `docker compose -f compose.yaml -f compose.host.yaml up -d --build`.
7. Open `https://your-domain.com`, enter the hosting credentials, then use the
   roleplay login. This instance uses public demo verification codes.

Caddy obtains and renews HTTPS certificates. The host configuration requires
an access password and sets Secure cookies. Basic authentication protects the
login, assets and APIs. Use HTTPS for hosting credentials. The helper creates
`.env` with owner-only permissions and refuses to replace it. `.env.example`
contains placeholders for manual configuration.

With an existing reverse proxy, use the base Compose service and proxy to
127.0.0.1:3000, setting the access password and Secure cookies in its environment.
No Git ignore rules are used. Keep host-generated credentials and personal
account data on the host and outside public commits.

## Updates and troubleshooting

Run `git pull --ff-only`, then the same Compose command used to start the app.
Use `docker compose logs --tail=100 cashlarp` for app logs, or
`docker compose -f compose.yaml -f compose.host.yaml logs --tail=100 caddy`
for certificate/proxy errors. Check DNS, firewall rules and other services on
ports 80/443 if HTTPS cannot start. `docker compose down` preserves app data;
`docker compose down -v` deletes volumes and must not be used for updates.

## Back up and restore

For Docker, run `./scripts/backup.sh` to save a consistent SQLite snapshot under
`backups/`. For Python hosting, run:

```sh
python3 scripts/backup.py data/sandbox.sqlite3 /safe/location/cashlarp.sqlite3
```

The destination must not exist. The helper includes committed WAL data and
checks the snapshot. Keep a protected copy outside the VPS.

Keep the existing data and take a backup first. To restore a Docker snapshot:

```sh
docker compose stop cashlarp
docker compose run --rm --no-deps -v /absolute/path/to/backup.sqlite3:/restore/backup.sqlite3:ro cashlarp python -c 'import sqlite3; s=sqlite3.connect("file:/restore/backup.sqlite3?mode=ro",uri=True); d=sqlite3.connect("/app/data/sandbox.sqlite3"); s.backup(d); d.close(); s.close()'
docker compose start cashlarp
```

For Python hosting, stop the process and point `--db` at a copy of the verified
snapshot. Never replace SQLite files while the app is running.
