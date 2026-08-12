# Operational Runbooks

## Overview
This document contains step-by-step procedures for handling common production incidents in FuelRoute Pro.

---

## 🔴 High Error Rate

**Symptoms**: 5xx errors spike in Sentry/health endpoints, users report failures

**Triage**:
1. Check Sentry for error pattern:
   - Filter by `level:error` + last 15 min
   - Group by `type` or `culprit`
   - Note if single endpoint or widespread

2. Check health endpoints:
   ```bash
   curl http://localhost:8000/health/live/
   curl http://localhost:8000/health/ready/
   curl http://localhost:8000/api/v1/health/
   ```

3. Check external API status:
   - OSRM: `curl https://router.project-osrm.org/route/v1/driving/-87.6,41.8;-87.5,41.9`
   - Photon: `curl "https://photon.komoot.io/api/?q=Chicago,IL&limit=1&countrycode=us"`

**Resolution**:

| Root Cause | Action |
|------------|--------|
| **OSRM/Photon down** | Failover to next provider (if configured) or wait for recovery. Circuit breaker auto-recovers after 60s. |
| **DB connection pool exhausted** | Check PgBouncer: `docker compose exec pgbouncer psql -U fuelroute -c "SHOW POOLS;"` |
| **Long-running queries** | Check `pg_stat_activity` for queries > 30s; kill if needed |
| **App code bug** | Check Sentry stack trace; hotfix + deploy |

**Escalation**: If > 5% error rate for > 5 min → page on-call

---

## 🟡 High Latency (p95 > 2s)

**Symptoms**: API responses slow, users report timeouts

**Triage**:
1. Check cache hit rate:
   ```bash
   docker compose exec redis redis-cli INFO stats | grep keyspace_hits
   docker compose exec redis redis-cli INFO stats | grep keyspace_misses
   # Hit rate = hits / (hits + misses)
   ```

2. Check DB slow query log:
   ```bash
   docker compose exec db psql -U fuelroute -c "
     SELECT query, calls, mean_exec_time, max_exec_time
     FROM pg_stat_statements
     WHERE mean_exec_time > 100
     ORDER BY mean_exec_time DESC LIMIT 10;"
   ```

3. Check external API latency:
   ```bash
   time curl -s -o /dev/null -w "%{time_total}" \
     "https://router.project-osrm.org/route/v1/driving/-87.6,41.8;-87.5,41.9"
   ```

**Resolution**:

| Cause | Action |
|-------|--------|
| **Low cache hit rate** | Run `python manage.py warm_cache`; investigate cache invalidation |
| **Slow DB queries** | Add missing indexes; consider materialized views for stats |
| **OSRM/Photon slow** | Circuit breaker opens → fallback; consider self-hosted OSRM |
| **CPU/memory pressure** | Scale web workers: `docker compose up -d --scale web=3` |

---

## 🟠 Cache Stampede / Cache Miss Storm

**Symptoms**: Sudden latency spike after deploy/cache clear; Redis CPU 100%

**Triage**:
1. Check Redis:
   ```bash
   docker compose exec redis redis-cli INFO cpu
   docker compose exec redis redis-cli MONITOR | head -20
   ```

**Resolution**:
1. **Flush Redis** (if corruption suspected):
   ```bash
   docker compose exec redis redis-cli FLUSHDB
   ```
2. **Run warm_cache**:
   ```bash
   docker compose exec web python manage.py warm_cache
   ```
3. **Monitor recovery**:
   ```bash
   watch -n 2 'curl -s http://localhost:8000/api/v1/health/ | jq .cache'
   ```

**Prevention**: Stagger cache invalidation; use `cache.set(key, value, timeout)` with jitter

---

## 🔵 Database Full / Disk Space

**Symptoms**: "No space left on device", writes failing

**Triage**:
1. Check disk:
   ```bash
   df -h
   docker compose exec db psql -U fuelroute -c "SELECT pg_size_pretty(pg_database_size('fuelroute'));"
   ```

2. Check largest tables:
   ```bash
   docker compose exec db psql -U fuelroute -c "
     SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
     FROM pg_tables
     WHERE schemaname = 'public'
     ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"
   ```

**Resolution**:

| Cause | Action |
|-------|--------|
| **RouteCache/GeocodeCache bloated** | `DELETE FROM core_routecache WHERE created_at < NOW() - INTERVAL '30 days';` |
| **Old RoutePlan data** | Archive to cold storage: `pg_dump -t core_routeplan --where="created_at < '2025-01-01'" > archive.dump` |
| **WAL files accumulating** | Check `archive_mode` + `archive_command`; ensure backup service running |
| **General bloat** | `VACUUM ANALYZE VERBOSE;` (run during low traffic) |

**Emergency**: If disk > 90%, immediately:
```bash
# 1. Flush Redis
docker compose exec redis redis-cli FLUSHDB

# 2. Clean old caches
docker compose exec db psql -U fuelroute -c "DELETE FROM core_routecache WHERE created_at < NOW() - INTERVAL '7 days';"

# 3. Vacuum
docker compose exec db psql -U fuelroute -c "VACUUM (ANALYZE, VERBOSE) core_routecache;"
```

---

## 🟣 PgBouncer Connection Issues

**Symptoms**: "Too many connections", connection timeouts

**Triage**:
```bash
docker compose exec pgbouncer psql -U fuelroute -c "SHOW POOLS;"
docker compose exec pgbouncer psql -U fuelroute -c "SHOW CLIENTS;"
docker compose exec pgbouncer psql -U fuelroute -c "SHOW SERVERS;"
```

**Resolution**:
1. Check for connection leaks in app (ensure `connection.close()`)
2. Increase `DEFAULT_POOL_SIZE` in docker-compose (max 25 per instance)
3. Add more web workers (each needs ~2-3 connections)
4. Check for long-running transactions holding connections

---

## 🟤 Security Incidents

### Suspicious API Usage
1. Check rate limiting:
   ```bash
   # Check for IP making > 100 req/min
   tail -f /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn
   ```
2. Block at WAF/Cloudflare if needed

### Potential Data Breach
1. Rotate all secrets immediately (see `SECRET_ROTATION.md`)
2. Audit DB access logs
3. Check Sentry for unauthorized access patterns
4. Notify security team

---

## 📋 Post-Incident Checklist

After ANY production incident:

- [ ] Document timeline in incident log
- [ ] Root cause analysis within 24h
- [ ] Action items assigned with owners
- [ ] Runbook updated if new scenario
- [ ] Metrics/alerts added to prevent recurrence
- [ ] Team retrospective (blameless)

---

## Quick Reference Commands

```bash
# Health checks
curl -s http://localhost:8000/health/live/
curl -s http://localhost:8000/health/ready/ | jq .

# Logs
docker compose logs -f web
docker compose logs -f db
docker compose logs -f redis

# Restart services
docker compose restart web
docker compose restart db redis pgbouncer

# Scale web
docker compose up -d --scale web=3

# Shell access
docker compose exec web bash
docker compose exec db psql -U fuelroute -d fuelroute
docker compose exec redis redis-cli

# Cache operations
docker compose exec web python manage.py warm_cache
docker compose exec redis redis-cli FLUSHDB
```

---

## Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-08-12 | 1.0 | Siddhant | Initial version |