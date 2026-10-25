# Production setup boundary

The app remains available locally at http://127.0.0.1:5173. No public deployment has been performed.

For a production environment, set `APP_ENV=production` and configure all of the following before starting:

- A random `JWT_SECRET_KEY` of at least 48 characters, with HS256.
- Explicit HTTPS application origins in `CORS_ORIGINS`.
- A private PostgreSQL password and database URL.
- A working AI provider and key, plus semantic embeddings rather than the hash fixture baseline.

Startup fails if these requirements are missing. This check prevents accidental deployment of the open local configuration; it is not a substitute for operating a secure service.

Create an administrator deliberately from an operator terminal with `python -m app.admin email full_name`. The command prompts for the password and does not claim existing reports. Public registration always creates analyst accounts in production, even when the user table is empty. Development keeps its previous first-user convenience.

Keep Compose services on loopback behind an HTTPS proxy. Before inviting public users, complete password recovery/session revocation, shared rate and spending limits, backup-and-restore drills, data retention/deletion controls, monitoring and independently reviewed real-report acceptance tests. See the [product plan](PRODUCT_PLAN.md) and [acceptance evidence](REAL_REPORT_CHECKS.md).
