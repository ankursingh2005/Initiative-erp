# Daily PostgreSQL backup

Prepared implementation; it does not activate backups until a Render cron job
and private storage are configured. The existing web service is unaffected.

The job exports a consistent PostgreSQL custom-format archive, checks that
`pg_restore` can read its contents, uploads it with AES256 server-side encryption,
checks remote size, and uploads a SHA-256 checksum. A failed step exits nonzero.
Archive checks are not a substitute for a successful test restore.

## Activate on Render

1. Confirm the production database's PostgreSQL major version and region in
   Render. The Dockerfile defaults to client version 18; change its default to
   match your database before deploying. An older client cannot dump a newer
   server. Use a direct database URL, not a connection-pooler URL.
2. Create a private Amazon S3 bucket with Block Public Access enabled and default
   encryption. Give the backup identity `s3:PutObject` and `s3:GetObject` only on
   `arn:aws:s3:::YOUR_BUCKET/erp-backups/*`. It does not need permission to delete
   backups. Use a dedicated identity, not your AWS root credentials.
3. Configure an S3 lifecycle rule scoped to `erp-backups/`: expire current objects
   after 30 days and abort incomplete multipart uploads after 7 days. If bucket
   versioning is enabled, configure noncurrent-version expiration too. This job
   itself never deletes remote backups. Retention needs this separate bucket rule.
4. Push these files to the repository used by Render. Create **New > Cron Job**,
   using that repository, Docker runtime, and the same region as the database.
   Dockerfile path: `deploy/backup/Dockerfile`; Docker build context: repository
   root. Keep the image's default startup command.
5. Set schedule **`30 20 * * *`**. Render schedules use UTC: this is **2 AM IST
   every day**. Set these environment variables in the cron job, not in Git:

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | Production database's direct internal connection URL |
   | `S3_BUCKET_NAME` | Your private backup bucket |
   | `AWS_DEFAULT_REGION` | Bucket's AWS region |
   | `AWS_ACCESS_KEY_ID` | Dedicated backup identity's access key |
   | `AWS_SECRET_ACCESS_KEY` | Its secret key |
   | `BACKUP_PREFIX` | `erp-backups` (default) |

   Optional `S3_ENDPOINT_URL` supports an HTTPS S3-compatible endpoint, provided
   it supports the job's AES256 encryption and object metadata operations.
6. Configure Render job-failure notifications to an account you monitor. Click
   **Trigger Run**, verify success in Runs, and confirm both files in the bucket.
7. Complete a test restore below before relying on this backup. Also verify that
   the following scheduled run succeeds. Periodically repeat the restore drill.

Render cron jobs have a minimum charge of $1/month, separate from web hosting.
Database and object storage charges are also separate. No paid resource is
created by adding these files.

## Restore drill / recovery

1. Download a matching `.dump` and `.dump.sha256` into a private local directory.
   Run `sha256sum --check BACKUP_FILENAME.dump.sha256` there.
2. Create an **empty, separate PostgreSQL database** with a compatible version.
   Do not restore into production or an existing populated database.
3. Set `PGDATABASE` securely in your terminal environment to the new database's
   connection URL. Do not paste credentials into shared logs or this document.
4. Run `pg_restore --exit-on-error --single-transaction --no-owner --no-acl
   --dbname="$PGDATABASE" BACKUP_FILENAME.dump` (one command on one line).
5. Check table counts and recent attendance, employees, sales, schemes and
   attachments. Test an isolated ERP instance against this database, with
   scheduled messages/integrations disabled, before considering a production
   switch. Application startup can apply migrations, so use the matching code
   revision and retain the original database until verification is complete.
6. Only after validation, update the production web service's `DATABASE_URL` to
   the restored database and redeploy. Keep secrets and configuration separately;
   this database dump does not export roles, grants, or Render environment values.

## Coverage

All schemas/data accessible to the database connection are dumped, including
database-backed employee records, attendance selfies and scheme attachments.
Browser-only incentive uploads/saved reports in IndexedDB are **not** database
data and are not included. Files outside PostgreSQL, source code, external
services, and Render secrets need their own recovery copies.

Paid Render PostgreSQL also has built-in point-in-time recovery. Verify it on
the database's **Recovery** page; buying a paid web service alone does not
establish that the database has a paid plan.

Sources:
- https://render.com/docs/postgresql-backups
- https://render.com/docs/backup-postgresql-to-s3
- https://render.com/docs/cronjobs
