PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_signature TEXT NOT NULL,
    correction_payload TEXT NOT NULL,
    confidence_before REAL NOT NULL CHECK(confidence_before >= 0 AND confidence_before <= 1),
    confidence_after REAL NOT NULL CHECK(confidence_after >= 0 AND confidence_after <= 1),
    context_metadata TEXT NOT NULL DEFAULT '{}',
    rule_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    optional_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_corrections_pattern_signature
    ON corrections(pattern_signature);

CREATE INDEX IF NOT EXISTS idx_corrections_confidence_before
    ON corrections(confidence_before);

CREATE TRIGGER IF NOT EXISTS trg_corrections_updated_at
AFTER UPDATE ON corrections
FOR EACH ROW
BEGIN
    UPDATE corrections
    SET updated_at = datetime('now')
    WHERE id = NEW.id;
END;

CREATE TABLE IF NOT EXISTS rule_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correction_id INTEGER NOT NULL,
    target_pattern_signature TEXT NOT NULL,
    similarity_threshold REAL NOT NULL CHECK(similarity_threshold >= 0 AND similarity_threshold <= 1),
    computed_similarity REAL NOT NULL CHECK(computed_similarity >= 0 AND computed_similarity <= 1),
    reuse_success INTEGER NOT NULL CHECK(reuse_success IN (0, 1)),
    outcome_reason TEXT NOT NULL,
    context_metadata TEXT NOT NULL DEFAULT '{}',
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    optional_notes TEXT,
    FOREIGN KEY(correction_id) REFERENCES corrections(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rule_history_correction_id
    ON rule_history(correction_id);

CREATE INDEX IF NOT EXISTS idx_rule_history_target_pattern_signature
    ON rule_history(target_pattern_signature);
