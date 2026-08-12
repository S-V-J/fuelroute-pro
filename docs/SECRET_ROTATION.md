# Secret Rotation Runbook

## Overview
This document describes the procedures for rotating secrets in FuelRoute Pro. All secrets are managed through environment variables in the deployment platform (GitHub Environments, AWS Secrets Manager, or Kubernetes).

---

## DJANGO_SECRET_KEY

**Rotation Frequency**: Every 90 days or immediately if compromised

**Impact**: Invalidates all user sessions, CSRF tokens, and signed cookies.

**Procedure**:
1. Generate new key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
2. Update secret in deployment platform:
   - GitHub: Settings → Environments → production → `DJANGO_SECRET_KEY`
   - AWS Secrets Manager: Update secret value
   - Kubernetes: Update SealedSecret/ExternalSecret
3. Deploy (rolling restart — invalidates all sessions):
   ```bash
   # Kubernetes
   kubectl rollout restart deployment/fuelroute-pro
   
   # Docker Compose
   docker compose up -d --force-recreate
   ```
4. Notify team via #infra channel

---

## DATABASE_URL (PostgreSQL Password)

**Rotation Frequency**: Every 90 days or per compliance requirements

**Impact**: Requires coordinated rotation of web app + PgBouncer.

**Procedure**:
1. Generate new password in AWS Secrets Manager / pgAdmin / PostgreSQL:
   ```sql
   ALTER USER fuelroute WITH PASSWORD 'new_secure_password';
   ```
2. Update `DATABASE_URL` secret in deployment platform:
   - Format: `postgresql://fuelroute:NEW_PASSWORD@pgbouncer:6432/fuelroute`
3. Rolling deploy web + pgbouncer:
   ```bash
   # Kubernetes
   kubectl rollout restart deployment/fuelroute-pro deployment/pgbouncer
   
   # Docker Compose
   docker compose up -d --force-recreate
   ```
4. Verify connectivity:
   ```bash
   curl http://localhost:8000/health/ready/
   ```
5. Revoke old password after confirming deploy success (optional — PostgreSQL supports multiple active passwords if using `ALTER USER ... VALID UNTIL`)

---

## API Keys (ORS, GraphHopper, SendGrid, Sentry)

**Rotation Frequency**: Per provider recommendation (typically 90-365 days)

**Impact**: Brief period where old/new keys may both need to be valid during rolling deploy.

**Procedure**:
1. Create new key in provider dashboard
2. Update secret in deployment platform
3. Deploy
4. Verify functionality:
   - ORS/GraphHopper: Test `/api/v1/providers/` shows key configured
   - SendGrid: Trigger password reset email
   - Sentry: Trigger test error in staging
4. Revoke old key after confirming deploy success

---

## Emergency Rotation (Compromise)

If a secret is suspected compromised:

1. **Immediately** generate and deploy new secret (skip normal schedule)
2. Revoke compromised key **immediately** in provider dashboard
3. Audit logs for unauthorized access during exposure window
4. Document incident in security log
5. Conduct post-incident review

---

## Verification Checklist

After any rotation:
- [ ] All health endpoints return 200
- [ ] Sample route plan works (`/api/v1/plan/`)
- [ ] User login/logout works
- [ ] No Sentry alerts for "Invalid CSRF" or "Bad signature"
- [ ] PgBouncer pool shows healthy connections