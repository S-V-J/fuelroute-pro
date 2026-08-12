# Disaster Recovery Plan

## RPO/RTO Targets

| Metric | Target | Implementation |
|--------|--------|----------------|
| **RPO** (Recovery Point Objective) | 1 hour | Automated daily backups + WAL archiving |
| **RTO** (Recovery Time Objective) | 30 minutes | Pre-provisioned infrastructure + automated restore scripts |

---

## Backup Architecture

### Primary Backups
- **Service**: `prodrigestivill/postgres-backup-local:16` in docker-compose
- **Schedule**: Daily at 02:00 UTC
- **Retention**: 30 days
- **Storage**: Local volume (`./backups`) with optional S3 sync
- **Format**: Compressed PostgreSQL custom format (`.dump`)

### WAL Archiving (Point-in-Time Recovery)
- **Method**: `pg_basebackup` + WAL files
- **RPO**: < 1 hour (WAL segments shipped to S3 every 5 min)
- **Enable**: Set `BACKUP_S3_BUCKET` + AWS credentials in docker-compose

---

## Restore Procedure

### Scenario 1: Full Database Restore (From Latest Daily Backup)

**Prerequisites**: 
- Access to backup storage (`./backups` or S3)
- New PostgreSQL instance running
- Docker Compose or Kubernetes environment

**Steps**:
1. **Provision new PostgreSQL instance** (if needed):
   ```bash
   # Docker Compose
   docker compose up -d db
   
   # Wait for healthy
   docker compose exec db pg_isready -U fuelroute -d fuelroute
   ```

2. **Identify latest backup**:
   ```bash
   # Local
   ls -lt ./backups/*.dump | head -1
   
   # S3 (if configured)
   aws s3 ls s3://${BACKUP_S3_BUCKET}/fuelroute/ | sort | tail -1
   ```

3. **Restore backup**:
   ```bash
   # Local restore
   docker compose exec -T db pg_restore \
     --clean --if-exists --no-owner --no-acl \
     -d fuelroute < ./backups/fuelroute_YYYYMMDD_HHMMSS.dump
   
   # S3 restore
   aws s3 cp s3://${BACKUP_S3_BUCKET}/fuelroute/fuelroute_YYYYMMDD_HHMMSS.dump - | \
     docker compose exec -T db pg_restore \
     --clean --if-exists --no-owner --no-acl -d fuelroute
   ```

4. **Update DATABASE_URL secret** (if changed):
   ```bash
   # GitHub Environment / AWS Secrets Manager
   # Update to point to new DB instance
   ```

5. **Deploy web application** (migrations auto-run):
   ```bash
   docker compose up -d web
   # Or Kubernetes: kubectl rollout restart deployment/fuelroute-pro
   ```

6. **Verify**:
   ```bash
   curl http://localhost:8000/health/ready/
   curl -X POST http://localhost:8000/api/v1/plan/ \
     -H "Content-Type: application/json" \
     -d '{"start": "Chicago, IL", "finish": "Dallas, TX"}'
   ```

---

### Scenario 2: Point-in-Time Recovery (PITR)

**When**: Need to recover to specific timestamp (e.g., before bad data deletion)

**Steps**:
1. Restore latest base backup (as above)
2. **Replay WAL files to target timestamp**:
   ```bash
   # Create recovery.conf in PGDATA
   cat > /var/lib/postgresql/data/recovery.conf << EOF
   restore_command = 'aws s3 cp s3://${BACKUP_S3_BUCKET}/wal/%f %p'
   recovery_target_time = '2026-01-15 14:30:00 UTC'
   recovery_target_action = 'promote'
   EOF
   ```
3. Start PostgreSQL — it will replay WAL up to target time
4. Verify data integrity at target timestamp
5. Update `DATABASE_URL` and deploy

---

### Scenario 3: Single Table/Row Recovery

**When**: Accidental delete/update of specific data

**Steps**:
1. Restore latest backup to temporary database:
   ```bash
   docker compose exec db createdb -U fuelroute fuelroute_restore
   pg_restore -d fuelroute_restore -t core_routeplan ./backups/latest.dump
   ```
2. Extract needed data:
   ```sql
   -- Connect to temp DB
   SELECT * FROM core_routeplan WHERE id = 'target-uuid';
   ```
3. Insert into production:
   ```sql
   -- Connect to production
   INSERT INTO core_routeplan (...) VALUES (...);
   ```

---

## Monthly DR Drill

| Item | Detail |
|------|--------|
| **Schedule** | First Monday of month, 10:00 UTC |
| **Owner** | Platform Engineer (on-call) |
| **Duration** | ~45 minutes |
| **Environment** | Staging (separate from prod) |

**Drill Steps**:
1. [ ] Notify team: "Starting monthly DR drill — staging will be restored"
2. [ ] Provision fresh staging PostgreSQL
3. [ ] Restore latest backup to staging
4. [ ] Deploy web to staging (pointing to restored DB)
5. [ ] Verify:
   - [ ] Health endpoints: `/health/live/`, `/health/ready/`
   - [ ] Sample route plan: Chicago → Dallas
   - [ ] Station count matches production
   - [ ] RouteCache/GeocodeCache populate correctly
6. [ ] Document: Time to restore, time to verify, any issues
7. [ ] Clean up staging resources
8. [ ] Post results to #infra channel

**Success Criteria**: Full restore + verification < 30 minutes

---

## Backup Verification Checklist

Run monthly (can be combined with DR drill):

- [ ] Backup file exists and is non-zero
- [ ] Backup is valid PostgreSQL dump (`pg_restore --list backup.dump`)
- [ ] Backup contains all expected tables (`core_routeplan`, `core_station`, etc.)
- [ ] Row counts match production (±5% for recent data)
- [ ] S3 sync successful (if configured)
- [ ] Retention policy: only 30 most recent backups retained

---

## Contact & Escalation

| Role | Contact | When |
|------|---------|------|
| Primary On-Call | #infra-pager | All incidents |
| Platform Lead | @platform-lead | RTO at risk |
| Engineering Manager | @eng-mgr | Data loss suspected |

---

## Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-08-12 | 1.0 | Siddhant | Initial version |