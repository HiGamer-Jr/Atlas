\set ON_ERROR_STOP on
-- Deliberate offline post-restore policy, run only against a newly restored database.
-- Required psql variables: expected_database, technical_operator, incident_reference.
BEGIN;
SELECT set_config('hiatlas.restore.expected_database', :'expected_database', true);
SELECT set_config('hiatlas.restore.technical_operator', :'technical_operator', true);
SELECT set_config('hiatlas.restore.incident_reference', :'incident_reference', true);
DO $$
BEGIN
  IF current_database() <> current_setting('hiatlas.restore.expected_database')
     OR length(btrim(current_setting('hiatlas.restore.technical_operator'))) < 3
     OR length(btrim(current_setting('hiatlas.restore.incident_reference'))) < 3
     OR NOT EXISTS(SELECT 1 FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba
                   WHERE d.datname=current_database() AND r.rolname=current_user AND NOT r.rolsuper)
  THEN RAISE EXCEPTION 'Offline restored database identity or operator evidence rejected'; END IF;
END $$;
-- Preserve business records and append-only historical events.
UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,now());
UPDATE access_contexts SET revoked_at=COALESCE(revoked_at,now());
UPDATE support_sessions SET status='REVOKED',ended_at=now() WHERE status='ACTIVE';
UPDATE temporary_privileged_grants
 SET status='REVOKED',ended_at=now(),revoked_at=now(),version=version+1 WHERE status='ACTIVE';
DELETE FROM auth_preauth;
UPDATE security_tokens SET invalidated_at=now() WHERE consumed_at IS NULL AND invalidated_at IS NULL;
UPDATE email_outbox SET status='CANCELLED',ciphertext=NULL,failure_code='RESTORE_INVALIDATED',lease_expires_at=NULL
 WHERE status IN ('QUEUED','DISPATCHING');
INSERT INTO audit_events(actor_id,actor_role,action,outcome,request_id,reason,reference,after_state)
 VALUES(NULL,NULL,'identity.restore.invalidated','SUCCESS',gen_random_uuid(),
 'Offline restored database technical credential invalidation',
 current_setting('hiatlas.restore.incident_reference'),
 jsonb_build_object('technical_operator',current_setting('hiatlas.restore.technical_operator'),
                    'database_role',current_user,'policy','REVOKE_RESTORED_TECHNICAL_ACCESS'));
COMMIT;
