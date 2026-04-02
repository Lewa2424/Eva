-- Eva 2.0 MVP schema
-- Source of truth for MemoryManager tables.

BEGIN;

-- 1) tasks: входящие цели/задачи
CREATE TABLE IF NOT EXISTS tasks (
    id          BIGSERIAL PRIMARY KEY,
    goal        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    source      TEXT NOT NULL DEFAULT 'user',
    meta        JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);

-- 2) plans: планы по задачам
CREATE TABLE IF NOT EXISTS plans (
    id          BIGSERIAL PRIMARY KEY,
    task_id     BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    plan_text   TEXT NOT NULL,
    meta        JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plans_task_id     ON plans(task_id);
CREATE INDEX IF NOT EXISTS idx_plans_created_at  ON plans(created_at DESC);

-- 3) code_versions: версии кода (по модулям)
CREATE TABLE IF NOT EXISTS code_versions (
    id          BIGSERIAL PRIMARY KEY,
    module_name TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft', -- draft|active|deprecated etc.
    code_text   TEXT NOT NULL,
    meta        JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_code_versions_module_name ON code_versions(module_name);
CREATE INDEX IF NOT EXISTS idx_code_versions_created_at  ON code_versions(created_at DESC);

-- 4) test_results: результаты тестов (привязка к задаче и опционально к версии кода)
CREATE TABLE IF NOT EXISTS test_results (
    id              BIGSERIAL PRIMARY KEY,
    task_id          BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    code_version_id  BIGINT REFERENCES code_versions(id) ON DELETE SET NULL,
    status           TEXT NOT NULL, -- pass|fail|error
    output           TEXT,
    meta             JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_test_results_task_id        ON test_results(task_id);
CREATE INDEX IF NOT EXISTS idx_test_results_code_version   ON test_results(code_version_id);
CREATE INDEX IF NOT EXISTS idx_test_results_created_at     ON test_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_test_results_status         ON test_results(status);

-- 5) reflections: рефлексия/уроки по задаче
CREATE TABLE IF NOT EXISTS reflections (
    id          BIGSERIAL PRIMARY KEY,
    task_id     BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    reflection  TEXT NOT NULL,
    meta        JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reflections_task_id     ON reflections(task_id);
CREATE INDEX IF NOT EXISTS idx_reflections_created_at  ON reflections(created_at DESC);

COMMIT;
