CREATE TABLE IF NOT EXISTS gas_retail_loads (
    load_id TEXT PRIMARY KEY,
    reviewed_on TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    complete INTEGER NOT NULL CHECK (complete = 0),
    reuse_status TEXT NOT NULL CHECK (reuse_status = 'review_pending')
);
CREATE TABLE IF NOT EXISTS gas_retail_sources (
    load_id TEXT NOT NULL REFERENCES gas_retail_loads(load_id),
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    published_on TEXT,
    retrieved_on TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    file_name TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('pdf', 'html')),
    byte_size INTEGER NOT NULL CHECK (byte_size BETWEEN 1 AND 25000000),
    page_count INTEGER NOT NULL CHECK (page_count BETWEEN 0 AND 200),
    reuse_status TEXT NOT NULL CHECK (reuse_status = 'review_pending'),
    notes TEXT NOT NULL,
    PRIMARY KEY (load_id, source_id)
);
CREATE TABLE IF NOT EXISTS gas_retail_entities (
    load_id TEXT NOT NULL REFERENCES gas_retail_loads(load_id),
    gas_id TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('retailer', 'group', 'rest', 'total', 'direct_consumer', 'unknown')),
    review_note TEXT NOT NULL,
    PRIMARY KEY (load_id, gas_id)
);
CREATE TABLE IF NOT EXISTS gas_retail_mappings (
    load_id TEXT NOT NULL,
    mapping_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    observed_name TEXT NOT NULL,
    gas_id TEXT NOT NULL,
    review_note TEXT NOT NULL,
    PRIMARY KEY (load_id, mapping_id),
    UNIQUE (load_id, source_id, observed_name, gas_id),
    FOREIGN KEY (load_id, source_id) REFERENCES gas_retail_sources(load_id, source_id),
    FOREIGN KEY (load_id, gas_id) REFERENCES gas_retail_entities(load_id, gas_id)
);
CREATE TABLE IF NOT EXISTS gas_retail_audits (
    load_id TEXT NOT NULL REFERENCES gas_retail_loads(load_id),
    period TEXT NOT NULL,
    metric TEXT NOT NULL CHECK (metric IN ('clients', 'sales')),
    status TEXT NOT NULL CHECK (status IN ('not_reviewed', 'located', 'partial', 'reviewed', 'unavailable', 'source_error')),
    source_ids_json TEXT NOT NULL,
    pages_json TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (load_id, period, metric)
);
CREATE TABLE IF NOT EXISTS gas_retail_observations (
    load_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    mapping_id TEXT NOT NULL,
    month TEXT NOT NULL,
    metric TEXT NOT NULL CHECK (metric IN ('clients', 'sales')),
    scope TEXT NOT NULL CHECK (scope IN ('whole_market', 'liberalised', 'regulated')),
    unit TEXT NOT NULL CHECK (unit IN ('clients', 'MWh', 'GWh', 'kWh')),
    page INTEGER NOT NULL CHECK (page BETWEEN 1 AND 200),
    table_label TEXT NOT NULL,
    source_row TEXT NOT NULL,
    raw_value TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('exact', 'zero', 'missing', 'suppressed', 'source_error', 'bounded')),
    value TEXT,
    upper_bound TEXT,
    review_note TEXT NOT NULL,
    PRIMARY KEY (load_id, observation_id),
    FOREIGN KEY (load_id, source_id) REFERENCES gas_retail_sources(load_id, source_id),
    FOREIGN KEY (load_id, mapping_id) REFERENCES gas_retail_mappings(load_id, mapping_id),
    CHECK ((status IN ('exact', 'zero') AND value IS NOT NULL AND upper_bound IS NULL)
        OR (status = 'bounded' AND value IS NULL AND upper_bound IS NOT NULL)
        OR (status IN ('missing', 'suppressed', 'source_error') AND value IS NULL AND upper_bound IS NULL))
);
CREATE INDEX IF NOT EXISTS gas_retail_observations_period_idx
    ON gas_retail_observations(load_id, metric, scope, month);
CREATE TABLE IF NOT EXISTS gas_retail_quarters (
    load_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    gas_id TEXT NOT NULL,
    period TEXT NOT NULL,
    metric TEXT NOT NULL CHECK (metric IN ('clients', 'sales')),
    scope TEXT NOT NULL CHECK (scope IN ('whole_market', 'liberalised', 'regulated')),
    unit TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('exact', 'zero', 'missing', 'suppressed', 'source_error', 'bounded')),
    value TEXT,
    upper_bound TEXT,
    missing_months_json TEXT NOT NULL,
    input_statuses_json TEXT NOT NULL,
    observation_ids_json TEXT NOT NULL,
    PRIMARY KEY (load_id, source_id, gas_id, period, metric, scope, unit),
    FOREIGN KEY (load_id, source_id) REFERENCES gas_retail_sources(load_id, source_id),
    FOREIGN KEY (load_id, gas_id) REFERENCES gas_retail_entities(load_id, gas_id)
);
CREATE INDEX IF NOT EXISTS gas_retail_quarters_period_idx
    ON gas_retail_quarters(load_id, metric, scope, period);
CREATE INDEX IF NOT EXISTS gas_retail_quarters_company_idx
    ON gas_retail_quarters(load_id, gas_id, metric, scope, period);
CREATE INDEX IF NOT EXISTS gas_retail_mappings_company_idx
    ON gas_retail_mappings(load_id, gas_id, source_id);
CREATE TABLE IF NOT EXISTS gas_retail_catalogue (
    load_id TEXT NOT NULL,
    gas_id TEXT NOT NULL,
    observed_name TEXT NOT NULL,
    designation TEXT NOT NULL CHECK (designation = 'gas_cur'),
    source_id TEXT NOT NULL,
    page INTEGER NOT NULL CHECK (page BETWEEN 0 AND 200),
    evidence_on TEXT NOT NULL,
    review_note TEXT NOT NULL,
    PRIMARY KEY (load_id, gas_id, source_id),
    FOREIGN KEY (load_id, source_id) REFERENCES gas_retail_sources(load_id, source_id),
    FOREIGN KEY (load_id, gas_id) REFERENCES gas_retail_entities(load_id, gas_id)
);
CREATE TABLE IF NOT EXISTS gas_retail_source_audits (
    load_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    period TEXT NOT NULL,
    metric TEXT NOT NULL CHECK (metric IN ('clients', 'sales')),
    status TEXT NOT NULL,
    pages_json TEXT NOT NULL,
    table_review_status TEXT NOT NULL,
    retailer_coverage TEXT NOT NULL,
    geographic_scope TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (load_id, source_id, period, metric),
    FOREIGN KEY (load_id, source_id) REFERENCES gas_retail_sources(load_id, source_id)
);
CREATE TABLE IF NOT EXISTS gas_retail_unresolved_observations (
    load_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    mapping_id TEXT NOT NULL,
    period TEXT NOT NULL,
    metric TEXT NOT NULL CHECK (metric IN ('clients', 'sales')),
    scope TEXT NOT NULL,
    unit TEXT NOT NULL,
    page INTEGER NOT NULL CHECK (page BETWEEN 1 AND 200),
    table_label TEXT NOT NULL,
    source_row TEXT NOT NULL,
    raw_value TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'source_error'),
    review_note TEXT NOT NULL,
    PRIMARY KEY (load_id, observation_id),
    FOREIGN KEY (load_id, source_id) REFERENCES gas_retail_sources(load_id, source_id),
    FOREIGN KEY (load_id, mapping_id) REFERENCES gas_retail_mappings(load_id, mapping_id)
);
CREATE TABLE IF NOT EXISTS gas_retail_observation_details (
    load_id TEXT NOT NULL REFERENCES gas_retail_loads(load_id),
    observation_id TEXT NOT NULL,
    original_unit TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status IN ('reviewed', 'partial', 'source_error')),
    PRIMARY KEY (load_id, observation_id)
);
CREATE TABLE IF NOT EXISTS gas_retail_review_records (
    load_id TEXT NOT NULL REFERENCES gas_retail_loads(load_id),
    record_id TEXT NOT NULL,
    category TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (load_id, record_id)
);
