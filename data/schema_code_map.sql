BEGIN;

CREATE TABLE IF NOT EXISTS modules (
  id           BIGSERIAL PRIMARY KEY,
  name         TEXT NOT NULL UNIQUE,
  description  TEXT,
  file_path    TEXT NOT NULL,
  start_line   INT,
  end_line     INT,
  metrics      JSONB,
  status       TEXT NOT NULL DEFAULT 'unknown',

  -- Добавлено под текущий код MemoryManager/SelfMonitor:
  meta         JSONB,
  content_hash TEXT,
  last_seen_at TIMESTAMPTZ,

  created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS dependencies (
  id             BIGSERIAL PRIMARY KEY,
  from_module_id BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  to_module_id   BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  kind           TEXT NOT NULL DEFAULT 'call',  -- call|import|other
  created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (from_module_id, to_module_id, kind)
);

COMMIT;
