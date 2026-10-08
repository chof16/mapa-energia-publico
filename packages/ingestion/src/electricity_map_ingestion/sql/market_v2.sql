CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY);
INSERT INTO schema_migrations VALUES (2);
CREATE TABLE sectors (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE);
CREATE TABLE periods (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2099),
    quarter INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    UNIQUE (year, quarter)
);
CREATE TABLE licenses (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    url TEXT NOT NULL,
    UNIQUE (code, url)
);
CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    license_id INTEGER NOT NULL REFERENCES licenses(id),
    conditions_url TEXT NOT NULL,
    attribution TEXT NOT NULL,
    UNIQUE (url, license_id, conditions_url, attribution)
);
CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    sector_id INTEGER NOT NULL REFERENCES sectors(id),
    role TEXT NOT NULL CHECK (role IN ('distributor', 'marketer')),
    code TEXT NOT NULL,
    UNIQUE (sector_id, role, code)
);
CREATE TABLE company_names (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name TEXT,
    UNIQUE (company_id, name)
);
CREATE UNIQUE INDEX company_without_observed_name ON company_names(company_id) WHERE name IS NULL;
CREATE TABLE tariffs (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE);
CREATE TABLE communities (code TEXT PRIMARY KEY CHECK (code BETWEEN '01' AND '19' AND length(code) = 2));
CREATE TABLE loads (
    id INTEGER PRIMARY KEY,
    sector_id INTEGER NOT NULL REFERENCES sectors(id),
    period_id INTEGER NOT NULL REFERENCES periods(id),
    source_id INTEGER NOT NULL REFERENCES sources(id),
    package_name TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    metadata_modified TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    loaded_at TEXT NOT NULL,
    UNIQUE (sector_id, period_id)
);
CREATE TABLE market_rows (
    load_id INTEGER NOT NULL REFERENCES loads(id) ON DELETE CASCADE,
    source_row_id INTEGER NOT NULL,
    distributor_name_id INTEGER NOT NULL REFERENCES company_names(id),
    marketer_name_id INTEGER REFERENCES company_names(id),
    category TEXT NOT NULL CHECK (category IN ('marketer', 'direct_consumer', 'unavailable')),
    tariff_id INTEGER NOT NULL REFERENCES tariffs(id),
    community_code TEXT NOT NULL REFERENCES communities(code),
    supplies INTEGER NOT NULL CHECK (supplies >= 0),
    energy_kwh INTEGER NOT NULL,
    PRIMARY KEY (load_id, source_row_id),
    CHECK ((category = 'marketer') = (marketer_name_id IS NOT NULL))
);
CREATE INDEX market_by_load_community ON market_rows(load_id, community_code, marketer_name_id);
CREATE INDEX market_by_marketer_load ON market_rows(marketer_name_id, load_id, community_code);
CREATE TABLE load_company_names (
    load_id INTEGER NOT NULL REFERENCES loads(id) ON DELETE CASCADE,
    name_id INTEGER NOT NULL REFERENCES company_names(id),
    extinct_mark INTEGER NOT NULL CHECK (extinct_mark IN (0, 1)),
    PRIMARY KEY (load_id, name_id, extinct_mark)
);
CREATE TABLE ingestion_issues (
    load_id INTEGER NOT NULL,
    source_row_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    PRIMARY KEY (load_id, source_row_id, kind),
    FOREIGN KEY (load_id, source_row_id) REFERENCES market_rows(load_id, source_row_id) ON DELETE CASCADE
);
CREATE VIEW loads_view AS
SELECT s.code AS sector, printf('%04dT%d', p.year, p.quarter) AS period,
       l.package_name, l.resource_id, l.metadata_modified, l.row_count, l.loaded_at,
       src.url AS source_url, lic.code AS license_id, lic.url AS license_url,
       src.conditions_url, src.attribution
FROM loads l JOIN sectors s ON s.id = l.sector_id JOIN periods p ON p.id = l.period_id
JOIN sources src ON src.id = l.source_id JOIN licenses lic ON lic.id = src.license_id;
CREATE VIEW market_rows_view AS
SELECT s.code AS sector, printf('%04dT%d', p.year, p.quarter) AS period,
       r.source_row_id AS source_id, d.code AS distributor_code, dn.name AS distributor_name,
       m.code AS marketer_code, mn.name AS marketer_name, r.category, t.code AS tariff,
       r.community_code, r.supplies, r.energy_kwh
FROM market_rows r JOIN loads l ON l.id = r.load_id JOIN periods p ON p.id = l.period_id
JOIN sectors s ON s.id = l.sector_id
JOIN company_names dn ON dn.id = r.distributor_name_id JOIN companies d ON d.id = dn.company_id
LEFT JOIN company_names mn ON mn.id = r.marketer_name_id LEFT JOIN companies m ON m.id = mn.company_id
JOIN tariffs t ON t.id = r.tariff_id;
CREATE VIEW company_names_view AS
SELECT s.code AS sector, printf('%04dT%d', p.year, p.quarter) AS period,
       c.role, c.code AS company_code, n.name AS observed_name, o.extinct_mark
FROM load_company_names o JOIN loads l ON l.id = o.load_id
JOIN sectors s ON s.id = l.sector_id JOIN periods p ON p.id = l.period_id
JOIN company_names n ON n.id = o.name_id JOIN companies c ON c.id = n.company_id;
CREATE VIEW ingestion_issues_view AS
SELECT s.code AS sector, printf('%04dT%d', p.year, p.quarter) AS period,
       i.source_row_id AS source_id, i.kind, i.detail
FROM ingestion_issues i JOIN loads l ON l.id = i.load_id
JOIN sectors s ON s.id = l.sector_id JOIN periods p ON p.id = l.period_id;
