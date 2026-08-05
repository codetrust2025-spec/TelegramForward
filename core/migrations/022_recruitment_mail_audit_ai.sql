-- Ollama-assisted mail audit: its own queue, its own cache, its own results.
--
-- Deliberately shares no table with the interview auto-booking feature. The
-- booking pipeline's queue (mailbox_sync_jobs), its analyses
-- (interview_mail_analyses) and its audit trail (interview_auto_booking_audit)
-- are neither written nor referenced here. Dropping every object in this file
-- would leave auto-booking completely intact.

CREATE TABLE IF NOT EXISTS mail_audit_ai_queue (
  id text PRIMARY KEY,
  finding_id text NOT NULL REFERENCES mail_outcome_audit_findings(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'PENDING',
  attempts integer NOT NULL DEFAULT 0,
  requested_by text,
  last_error text,
  retry_after timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  -- One pending review per finding: the audit never multiplies its own work.
  CONSTRAINT mail_audit_ai_queue_finding_unique UNIQUE (finding_id),
  CONSTRAINT mail_audit_ai_queue_status_check
    CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED','DEFERRED'))
);

-- Advisory second opinions. Nothing here overwrites a finding: the rule
-- engine's outcome stands until a human decides otherwise.
CREATE TABLE IF NOT EXISTS mail_audit_ai_results (
  id text PRIMARY KEY,
  cache_key text NOT NULL UNIQUE,
  finding_id text NOT NULL REFERENCES mail_outcome_audit_findings(id) ON DELETE CASCADE,
  prompt_name text NOT NULL,
  model text,
  agrees boolean NOT NULL DEFAULT true,
  suggested_outcome text,
  confidence double precision NOT NULL DEFAULT 0,
  reasoning text,
  is_bulk_campaign boolean NOT NULL DEFAULT false,
  sender_is_hiring_company boolean NOT NULL DEFAULT false,
  quoted_evidence text,
  raw_response jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Separate log. Booking keeps recruitment_audit_log; this never writes there.
CREATE TABLE IF NOT EXISTS mail_audit_ai_log (
  id text PRIMARY KEY,
  event text NOT NULL,
  finding_id text,
  detail text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mail_audit_ai_queue_status
  ON mail_audit_ai_queue(status, created_at);
CREATE INDEX IF NOT EXISTS idx_mail_audit_ai_results_finding
  ON mail_audit_ai_results(finding_id);
CREATE INDEX IF NOT EXISTS idx_mail_audit_ai_results_disagree
  ON mail_audit_ai_results(agrees, confidence DESC);
