CREATE TABLE snapshot (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    snapshot_date TEXT NOT NULL,
    complete INTEGER NOT NULL CHECK (complete = 0)
);
CREATE TABLE distributor_identity (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    registry_source_url TEXT NOT NULL
);
CREATE TABLE group_association (
    distributor_code TEXT PRIMARY KEY REFERENCES distributor_identity(code),
    group_name TEXT NOT NULL,
    evidence_json TEXT NOT NULL
);
CREATE TABLE claim_decision (
    id TEXT PRIMARY KEY,
    province_code TEXT NOT NULL,
    distributor_code TEXT NOT NULL REFERENCES distributor_identity(code),
    status TEXT NOT NULL CHECK (status IN ('accepted', 'rejected', 'superseded')),
    decision_reason TEXT NOT NULL CHECK (length(decision_reason) > 0),
    review_source_url TEXT NOT NULL,
    checked_on TEXT NOT NULL,
    evidence_json TEXT,
    CHECK (status != 'accepted' OR evidence_json IS NOT NULL)
);
CREATE UNIQUE INDEX one_accepted_claim_per_distributor_province
    ON claim_decision(province_code, distributor_code) WHERE status = 'accepted';
CREATE INDEX claim_decision_lookup ON claim_decision(status, province_code);
