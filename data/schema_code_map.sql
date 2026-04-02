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
  ast_synced_at TIMESTAMPTZ,
  calls_synced_at TIMESTAMPTZ,

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

CREATE TABLE IF NOT EXISTS code_entities (
  id              BIGSERIAL PRIMARY KEY,
  module_id       BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  entity_type     TEXT NOT NULL,                -- function|async_function|class|method|async_method
  name            TEXT NOT NULL,
  qualname        TEXT NOT NULL,
  parent_qualname TEXT,
  start_line      INT,
  end_line        INT,
  decorators      JSONB,
  docstring       TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_code_entities_module_id ON code_entities(module_id);
CREATE INDEX IF NOT EXISTS idx_code_entities_type ON code_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_code_entities_qualname ON code_entities(qualname);

CREATE TABLE IF NOT EXISTS module_imports (
  id             BIGSERIAL PRIMARY KEY,
  module_id      BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  import_type    TEXT NOT NULL,                 -- import|from
  imported_module TEXT,
  imported_name  TEXT,
  alias_name     TEXT,
  is_relative    BOOLEAN NOT NULL DEFAULT FALSE,
  relative_level INT NOT NULL DEFAULT 0,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_module_imports_module_id ON module_imports(module_id);
CREATE INDEX IF NOT EXISTS idx_module_imports_imported_module ON module_imports(imported_module);

CREATE TABLE IF NOT EXISTS entity_relations (
  id               BIGSERIAL PRIMARY KEY,
  source_module_id BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  target_module_id BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  from_entity_id   BIGINT NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
  to_entity_id     BIGINT NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
  relation_type    TEXT NOT NULL DEFAULT 'call',
  call_line        INT,
  call_expr        TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_relations_source_module_id ON entity_relations(source_module_id);
CREATE INDEX IF NOT EXISTS idx_entity_relations_target_module_id ON entity_relations(target_module_id);
CREATE INDEX IF NOT EXISTS idx_entity_relations_from_entity_id ON entity_relations(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_relations_to_entity_id ON entity_relations(to_entity_id);

CREATE TABLE IF NOT EXISTS entity_impacts (
  id                BIGSERIAL PRIMARY KEY,
  source_entity_id  BIGINT NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
  impacted_entity_id BIGINT NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
  source_module_id  BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  impacted_module_id BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  min_distance      INT NOT NULL DEFAULT 1,
  is_direct         BOOLEAN NOT NULL DEFAULT FALSE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (source_entity_id, impacted_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_impacts_source_entity_id ON entity_impacts(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_impacts_impacted_entity_id ON entity_impacts(impacted_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_impacts_source_module_id ON entity_impacts(source_module_id);
CREATE INDEX IF NOT EXISTS idx_entity_impacts_impacted_module_id ON entity_impacts(impacted_module_id);

CREATE TABLE IF NOT EXISTS module_impacts (
  id                BIGSERIAL PRIMARY KEY,
  source_module_id  BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  impacted_module_id BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  min_distance      INT NOT NULL DEFAULT 1,
  is_direct         BOOLEAN NOT NULL DEFAULT FALSE,
  via_kinds         JSONB,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (source_module_id, impacted_module_id)
);

CREATE INDEX IF NOT EXISTS idx_module_impacts_source_module_id ON module_impacts(source_module_id);
CREATE INDEX IF NOT EXISTS idx_module_impacts_impacted_module_id ON module_impacts(impacted_module_id);

CREATE TABLE IF NOT EXISTS entity_metrics (
  id                           BIGSERIAL PRIMARY KEY,
  entity_id                    BIGINT NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
  module_id                    BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  direct_entity_impact_count   INT NOT NULL DEFAULT 0,
  indirect_entity_impact_count INT NOT NULL DEFAULT 0,
  incoming_call_count          INT NOT NULL DEFAULT 0,
  criticality_score            NUMERIC(12, 2) NOT NULL DEFAULT 0,
  fragility_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  calculated_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (entity_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_metrics_entity_id ON entity_metrics(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_metrics_module_id ON entity_metrics(module_id);
CREATE INDEX IF NOT EXISTS idx_entity_metrics_criticality ON entity_metrics(criticality_score DESC);

CREATE TABLE IF NOT EXISTS module_metrics (
  id                           BIGSERIAL PRIMARY KEY,
  module_id                    BIGINT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
  direct_module_impact_count   INT NOT NULL DEFAULT 0,
  indirect_module_impact_count INT NOT NULL DEFAULT 0,
  incoming_dependency_count    INT NOT NULL DEFAULT 0,
  criticality_score            NUMERIC(12, 2) NOT NULL DEFAULT 0,
  fragility_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  calculated_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (module_id)
);

CREATE INDEX IF NOT EXISTS idx_module_metrics_module_id ON module_metrics(module_id);
CREATE INDEX IF NOT EXISTS idx_module_metrics_criticality ON module_metrics(criticality_score DESC);

CREATE TABLE IF NOT EXISTS state_snapshots (
  id                      BIGSERIAL PRIMARY KEY,
  reason                  TEXT NOT NULL DEFAULT 'scan',
  total_modules           INT NOT NULL DEFAULT 0,
  total_entities          INT NOT NULL DEFAULT 0,
  total_dependencies      INT NOT NULL DEFAULT 0,
  total_entity_relations  INT NOT NULL DEFAULT 0,
  total_entity_impacts    INT NOT NULL DEFAULT 0,
  total_module_impacts    INT NOT NULL DEFAULT 0,
  total_entity_metrics    INT NOT NULL DEFAULT 0,
  total_module_metrics    INT NOT NULL DEFAULT 0,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entity_metric_snapshots (
  id                           BIGSERIAL PRIMARY KEY,
  snapshot_id                  BIGINT NOT NULL REFERENCES state_snapshots(id) ON DELETE CASCADE,
  module_name                  TEXT NOT NULL,
  entity_qualname              TEXT NOT NULL,
  entity_type                  TEXT NOT NULL,
  direct_entity_impact_count   INT NOT NULL DEFAULT 0,
  indirect_entity_impact_count INT NOT NULL DEFAULT 0,
  incoming_call_count          INT NOT NULL DEFAULT 0,
  criticality_score            NUMERIC(12, 2) NOT NULL DEFAULT 0,
  fragility_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (snapshot_id, module_name, entity_qualname)
);

CREATE INDEX IF NOT EXISTS idx_entity_metric_snapshots_snapshot_id ON entity_metric_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_entity_metric_snapshots_entity_key ON entity_metric_snapshots(module_name, entity_qualname);

CREATE TABLE IF NOT EXISTS module_metric_snapshots (
  id                           BIGSERIAL PRIMARY KEY,
  snapshot_id                  BIGINT NOT NULL REFERENCES state_snapshots(id) ON DELETE CASCADE,
  module_name                  TEXT NOT NULL,
  direct_module_impact_count   INT NOT NULL DEFAULT 0,
  indirect_module_impact_count INT NOT NULL DEFAULT 0,
  incoming_dependency_count    INT NOT NULL DEFAULT 0,
  criticality_score            NUMERIC(12, 2) NOT NULL DEFAULT 0,
  fragility_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (snapshot_id, module_name)
);

CREATE INDEX IF NOT EXISTS idx_module_metric_snapshots_snapshot_id ON module_metric_snapshots(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_module_metric_snapshots_module_name ON module_metric_snapshots(module_name);

CREATE TABLE IF NOT EXISTS state_comparisons (
  id                     BIGSERIAL PRIMARY KEY,
  from_snapshot_id       BIGINT NOT NULL REFERENCES state_snapshots(id) ON DELETE CASCADE,
  to_snapshot_id         BIGINT NOT NULL REFERENCES state_snapshots(id) ON DELETE CASCADE,
  changed_entities_count INT NOT NULL DEFAULT 0,
  changed_modules_count  INT NOT NULL DEFAULT 0,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (from_snapshot_id, to_snapshot_id)
);

CREATE TABLE IF NOT EXISTS entity_metric_diffs (
  id                                 BIGSERIAL PRIMARY KEY,
  comparison_id                      BIGINT NOT NULL REFERENCES state_comparisons(id) ON DELETE CASCADE,
  module_name                        TEXT NOT NULL,
  entity_qualname                    TEXT NOT NULL,
  entity_type                        TEXT NOT NULL,
  is_added                           BOOLEAN NOT NULL DEFAULT FALSE,
  is_removed                         BOOLEAN NOT NULL DEFAULT FALSE,
  old_direct_entity_impact_count     INT NOT NULL DEFAULT 0,
  new_direct_entity_impact_count     INT NOT NULL DEFAULT 0,
  delta_direct_entity_impact_count   INT NOT NULL DEFAULT 0,
  old_indirect_entity_impact_count   INT NOT NULL DEFAULT 0,
  new_indirect_entity_impact_count   INT NOT NULL DEFAULT 0,
  delta_indirect_entity_impact_count INT NOT NULL DEFAULT 0,
  old_incoming_call_count            INT NOT NULL DEFAULT 0,
  new_incoming_call_count            INT NOT NULL DEFAULT 0,
  delta_incoming_call_count          INT NOT NULL DEFAULT 0,
  old_criticality_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  new_criticality_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  delta_criticality_score            NUMERIC(12, 2) NOT NULL DEFAULT 0,
  old_fragility_score                NUMERIC(12, 2) NOT NULL DEFAULT 0,
  new_fragility_score                NUMERIC(12, 2) NOT NULL DEFAULT 0,
  delta_fragility_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  created_at                         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (comparison_id, module_name, entity_qualname)
);

CREATE INDEX IF NOT EXISTS idx_entity_metric_diffs_comparison_id ON entity_metric_diffs(comparison_id);
CREATE INDEX IF NOT EXISTS idx_entity_metric_diffs_delta_criticality ON entity_metric_diffs(delta_criticality_score DESC);

CREATE TABLE IF NOT EXISTS module_metric_diffs (
  id                                 BIGSERIAL PRIMARY KEY,
  comparison_id                      BIGINT NOT NULL REFERENCES state_comparisons(id) ON DELETE CASCADE,
  module_name                        TEXT NOT NULL,
  is_added                           BOOLEAN NOT NULL DEFAULT FALSE,
  is_removed                         BOOLEAN NOT NULL DEFAULT FALSE,
  old_direct_module_impact_count     INT NOT NULL DEFAULT 0,
  new_direct_module_impact_count     INT NOT NULL DEFAULT 0,
  delta_direct_module_impact_count   INT NOT NULL DEFAULT 0,
  old_indirect_module_impact_count   INT NOT NULL DEFAULT 0,
  new_indirect_module_impact_count   INT NOT NULL DEFAULT 0,
  delta_indirect_module_impact_count INT NOT NULL DEFAULT 0,
  old_incoming_dependency_count      INT NOT NULL DEFAULT 0,
  new_incoming_dependency_count      INT NOT NULL DEFAULT 0,
  delta_incoming_dependency_count    INT NOT NULL DEFAULT 0,
  old_criticality_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  new_criticality_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  delta_criticality_score            NUMERIC(12, 2) NOT NULL DEFAULT 0,
  old_fragility_score                NUMERIC(12, 2) NOT NULL DEFAULT 0,
  new_fragility_score                NUMERIC(12, 2) NOT NULL DEFAULT 0,
  delta_fragility_score              NUMERIC(12, 2) NOT NULL DEFAULT 0,
  created_at                         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (comparison_id, module_name)
);

CREATE INDEX IF NOT EXISTS idx_module_metric_diffs_comparison_id ON module_metric_diffs(comparison_id);
CREATE INDEX IF NOT EXISTS idx_module_metric_diffs_delta_criticality ON module_metric_diffs(delta_criticality_score DESC);

COMMIT;
