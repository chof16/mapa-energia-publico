CREATE TABLE IF NOT EXISTS gas_network_loads (
    load_id TEXT PRIMARY KEY,
    period TEXT NOT NULL,
    source_url TEXT NOT NULL,
    download_url TEXT NOT NULL,
    source_title TEXT NOT NULL,
    published_on TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    reuse_status TEXT NOT NULL CHECK (reuse_status = 'review_pending'),
    row_count INTEGER NOT NULL CHECK (row_count > 0)
);
CREATE TABLE IF NOT EXISTS gas_network_rows (
    load_id TEXT NOT NULL REFERENCES gas_network_loads(load_id),
    source_row_id INTEGER NOT NULL CHECK (source_row_id > 0),
    province_code TEXT NOT NULL CHECK (length(province_code) = 2),
    municipality_name TEXT NOT NULL,
    distributor_name TEXT NOT NULL,
    supply_points INTEGER NOT NULL CHECK (supply_points >= 0),
    PRIMARY KEY (load_id, source_row_id)
);
CREATE INDEX IF NOT EXISTS gas_network_province_idx ON gas_network_rows(load_id, province_code, distributor_name);
