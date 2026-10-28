# Project guide for agents

## Scope

A public map of Spain, including the islands, Ceuta and Melilla, for exploring
electricity and gas distributors through a shared map UI. Electricity also has
retailer statistics, evolution and reference-retailer guidance. Gas is limited
to historical distributor network evidence under `/v1/gas/distribution`.
Gas retailer statistics, client counts, shares, censuses and regulated suppliers
are out of scope. Gas purchases and sales are deferred to a separate task.
Prices, offers, personal data and SIPS are out of scope.

## Working agreement

- Show every edit through Edit/Write or `apply_patch`; never edit files through
  shell commands. Use the terminal for inspection, Git, tests and builds.
- Keep the current branch during the session. Create a branch only at the start
  of a session or when explicitly requested. Do not work directly on `main`
  without authorization.
- Use `pnpm` for Node, `uv` for Python and Ruff for linting and formatting.
  Do not use npm, yarn or global Python package installations. Prefer `rg`,
  `fd` and `eza`.
- Write code, technical comments and agent instructions in English. Keep the
  public interface and functional documentation in Spanish.
- Never print or publish credentials, real `.env` files, databases, downloads
  or personal configuration. Examples use empty values or `example.org`.
- Validate inputs before handing them to a decoder: size, allowed format,
  signature where applicable, schema, and dimension or element limits. Do not
  trust a declared Content-Type. Preserve API, GeoJSON and ingestion validation.

## Structure

- `apps/web`: React, Vite, strict TypeScript and MapLibre.
- `apps/api`: FastAPI, SQLAlchemy and Pydantic DTOs organized by feature.
- `packages/domain`: rules independent of FastAPI and external sources.
- `packages/ingestion`: electricity CNMC Data ingestion/refresh and gas network annex import.
- `packages/map_pipeline`: cartographic preparation and PMTiles.
- `scripts`: database initialization, migration and export.
- `docs`: operating instructions and data rules.

API features (`electricity`, `gas`, `distribution`) follow the same separation:
`router.py` validates query DTOs, declares response types/errors, applies caching
and delegates; `service.py` performs bounded mapped SQLAlchemy reads;
`schemas.py`, `models.py` and `exceptions.py` own feature-specific contracts.
Declare route return annotations and keep application errors out of services.
Share the read-only `DatabaseSession` through root `dependencies.py` and common
query constraints, source/revision metadata and response fields through root
`schemas.py`; do not import those from another feature. Ordinary item lists use
limit 50 by default, at most 100, and offset 0–10,000 in both request and response
DTOs. Time-series endpoints retain their documented quarter-specific limits.

Electricity ingestion and the gas network importer share `cnmc_client.py` for
public CNMC transport and scalar validation. Keep source-specific
schemas and semantics in their importers; do not call another importer's private
helpers. Preserve byte limits before parsing, stable pagination, declared-total
checks, request identification and pauses. Persistence belongs in the matching
store module and writes run inside the importer's explicit transaction.
Name sector-specific ingestion modules and commands explicitly: `cnmc_electricity`,
`refresh_cnmc_electricity`, `electricity_store`, `gas_distribution` and
`gas_distribution_store`; use `ingest-cnmc-electricity`, `refresh-cnmc-electricity`
and `ingest-gas-distribution`. Do not use the ambiguous
`market` name for electricity-only backend modules. The canonical electricity API
is `/v1/electricity`; `/v1/market` remains a deprecated compatible alias for older
clients. The frontend uses `/v1/electricity`. Database table names remain stable. Keep OpenAPI
component names unique across features so a new gas DTO cannot rename an
established electricity response schema.

Organize React by feature (`map`, `electricity`, `gas`, `distribution`, `legal`), adding
`pages`, `layouts`, `components`, `hooks`, `actions`, `interfaces`, `lib`
and `store` only as needed. Keep page-specific UI in `pages/<page>/ui`.
Shared code belongs in `src/api`, `src/components`, `src/interfaces` and
`src/lib`; keep `main.tsx` and `app.router.tsx` in `src`.
Do not create empty directories. Components and hooks use `.tsx`; utilities
without JSX use `.ts`.
Electricity and gas must share the same map screen, territorial controls, panels
and interaction patterns. Reuse common UI with sector-specific data adapters;
do not create a separate gas dashboard or a different layout. Gas exposes only
distributor presence and its source, with no retailer, evolution or regulated-tariff
controls. Keep source scope and dates explicit without inventing geographic coverage.
On compact map screens, filters, distributor details and the legend start collapsed
and open on demand. Preserve accessible toggles, Escape-to-close behavior for details
and legend, the Canary Islands control, and direct touch panning. Keep this behavior
shared by both sectors, including when resizing or rotating the viewport.

## Contracts

- Gas exposes only `/v1/gas/distribution/provinces`,
  `/v1/gas/distribution/provinces/{province_code}` and
  `/v1/gas/distribution/revisions`. All use shared pagination and optional `load_id`.
  Do not retain unused gas statistical/census models, DTOs, routes or importers.
  Never infer distributor coverage from contact addresses or retailer totals.
- Gas network presence uses a separate, checksum-reviewed CNMC report annex for
  June 2019, covering natural-gas networks at most 4 bar. Install it explicitly
  with `ingest-gas-distribution`; never at API startup.
  Keep immutable `gas_network_loads` and source rows. Provincial API summaries
  group observed distributor names and sum supply points explicitly; repeated
  source rows remain separate. Exact reviewed province labels map to INE codes.
  The annex has no municipal INE codes: do not fuzzy-join or color municipalities,
  infer current identities, groups or exclusivity, or treat missing provinces as
  no network. Expose source month, publication date, hash and `complete=false`.
  Source reuse is `review_pending`, independent of CNMC Data; do not redistribute
  raw annexes or the combined database without reviewing the applicable terms.
- `/v1/electricity` and its `/v1/market` alias keep the normalized quarterly R2
  contract, including the existing `sector` parameter and empty/not-loaded
  behavior for absent gas data. They do not read `gas_*` tables or alias
  `/v1/gas`. Only introduce a common market
  contract when a source supports equivalent periods, identifiers and scope.
- Install gas network tables explicitly using the importer, never at API startup.
  The schema is additive to the existing normalized database. Do not import or
  publish electronic-office censuses, personal identities or contact addresses.
  CNMC Data and other CNMC sources retain independent reuse conditions.

- A distributor (distribuidora; R1 for electricity) operates the physical network;
  a retailer (comercializadora; R2 for electricity) sells energy. Multiple
  distributors can coexist in one municipality. Gas network supply points are
  not retailer client counts or individual CUPS identifiers.
- Electricity market data is national or regional. Do not infer provincial
  or municipal company coverage or consolidate companies without evidence.
- Distribution publishes only accepted positive claims with a source, date
  and confidence level. `complete=false` with an empty list means unknown.
  Provincial colors do not delineate the network and are hidden at municipal zoom.
- Electricity reference retailers (COR) have an independent catalogue; the
  regulated-tariff page does not publish tariff prices. Do not automatically
  associate them with distributors or invent exclusivity. Corporate affiliation
  and geographic presence require independent evidence.
- Preserve leading zeros in INE codes, exact joins by code, and the layers
  `municipios`, `provincias`, `ccaa` and `unidades_auxiliares`. Use dated
  current boundaries without presenting them as historical boundaries.
  Keep one point label per territory.
- Electricity URLs preserve filters and history within `/`, `/evolution` and
  `/regulated-tariff`; navigation between pages starts without the previous
  page's filters. Gas uses `/?sector=gas`; `/gas` is an entry alias. Legacy gas
  evolution or regulated-tariff links return to the gas map. Sector changes must
  not carry electricity identifiers or statistical filters into the gas contract.
- Unknown browser routes redirect to `/` with history replacement. Serve static
  crawler files before the SPA fallback. Keep the sitemap in sync with public
  pages and omit filters. Production builds use the frontend public directory;
  the map assets directory override applies only to local development.
- The shared footer links to `/cookies`, `/terms` and GitHub and states
  independence from CNMC and companies. Information pages do not mount maps
  or query the API. Keep cookie wording consistent with external resources
  actually used; the application includes no analytics, advertising or own cookies.
- Distinguish zero, missing data and null shares caused by a zero denominator.
  A valid R2 code takes precedence over a contradictory description. Preserve
  direct-consumer and unavailable categories, repeated rows and negative adjustments.
- Preserve company names as observed in each quarter. An extinction marker does
  not establish a deregistration date. Responses include sources and revisions.

## Data and local execution

Market data and distribution decisions share one normalized database:
local SQLite (`ENV=development`, `MAPA_DATABASE`) or PostgreSQL
(`MAPA_DATABASE_URL`, supported in both environments and taking precedence).
Production has no local fallback. PostgreSQL uses psycopg with read-only,
repeatable-read transactions and a bounded connection pool.
Do not create tables or run migrations at API startup. Local refreshes are
transactional; PostgreSQL schema and data are imported separately.

Use mapped SQLAlchemy models and `select()` expressions for API service queries,
including distribution. Do not use `text()` for those reads. Database setup and
ingestion retain their schema SQL and SQLite-specific transactional operations.

Aggregate normalized `market_rows` through load IDs and observed-name IDs so the
existing indexes apply. Do not outer-join `market_rows_view` for time series:
SQLite materializes the entire joined view. Preserve source-row multiplicity,
observed names and zero-versus-missing semantics when optimizing queries.

Optional Redis response caching uses server-only `MAPA_REDIS_URL` and
`MAPA_CACHE_TTL_SECONDS` (default 300). Cache keys include database identity,
operation and validated path/query parameters. Store complete response DTOs with
their revision metadata; never cache errors. Hits must avoid opening a database
connection and still enforce rate limits. Redis failures bypass the cache for
30 seconds. Concurrent misses are coalesced within one API process. Redis caching
does not make the in-memory rate limiter distributed. Local development without
a Redis URL always reads the database directly.

Public documentation explains local execution. The owner's account,
infrastructure and deployment configuration stays in `.local/`, ignored by
Git. Do not add it to the README, public examples or workflows. `VITE_*` values
are public and must never contain secrets. The in-memory rate limiter requires
one process and one instance; scaling requires a shared store.

The API is public, with no API-key authentication or token-based quota tiers.
Production defaults to 30 requests per IP per 60 seconds; `MAPA_API_REQUEST_LIMIT`
and `MAPA_API_WINDOW_SECONDS` are optional overrides. Development ignores quota
settings. CORS is supported in both environments via `MAPA_CORS_ORIGINS`;
development defaults to `http://localhost:5174` and `http://127.0.0.1:5174`,
while production requires explicit origins. The UI can also use the Vite proxy
with an empty `VITE_API_BASE_URL`. The private database connection URL is separate
from public API access and remains server-side.

Original code is licensed under AGPL-3.0-only; data retains its own terms.
Read the [data sources guide](docs/data-sources.md). Do not publish CNMC
electronic-office censuses or personal data. Do not evade source restrictions:
identify the client, use caching and pause between requests. Do not assign
CC BY-SA to third-party material without permission.

CNMC Data terms do not automatically apply to other CNMC websites, press
releases, registers or documents. Review those sources separately, including
facts and extracts in manifests and catalogues proposed for publication.
The combined database is not cleared for redistribution. Local export checks
verify consistency, not privacy or licensing, and do not sanitize the data.
Keep proposed cartographic downloads separate from database exports.

Attribute each dataset and download to its original publishing body and
preserve its source-specific reuse terms.

## Validation

`.github/workflows/ci.yml` runs `Python checks` (Ruff and pytest) and
`Web checks` (Vitest and the type-checked build) for pull requests and pushes
to `main`. Keep these job names stable: branch protection requires them.
CI uses synthetic data and does not need production secrets or downloaded maps.
Python CI starts an isolated Redis service and sets `TEST_REDIS_URL` for the
cross-instance cache integration test. Without that variable, only that test skips.
CI also runs an isolated PostgreSQL service with `TEST_POSTGRES_URL` to verify
synthetic API response parity and read-only transactions. That test uses a
temporary schema and skips locally without the variable; never point it at the
production database.
Python CI uses an available uv-managed Python 3.14 build; the local Arch patch
in `.python-version` may not be available as a managed download.

Run from the repository root after installing dependencies:

```sh
uv run --all-packages pytest
uv run ruff check .
uv run ruff format --check .
pnpm --dir apps/web test
pnpm --dir apps/web build
```

The build includes type checking. UI tests mock WebGL: inspect the map, Canary
Islands inset and mobile layout in a browser when changing them. Report what
was actually verified; a local build is not evidence of a remote deployment.

## Baseline and remaining work

Public code and local setup guides prepared on 2026-10-08; the owner selected
AGPL-3.0-only and English agent instructions before the first public commit.
The electricity snapshot contains 60 quarters (2011T1–2025T4), 1,426,773 rows
and distribution evidence for 48 of 52 provinces. Codes `09`, `12`, `35` and `47`
remain unknown for electricity. The separate June 2019 gas annex has 1,993 source
rows, 18 observed distributor names and evidence for 48 provinces; `35`, `38`,
`51` and `52` remain unknown in that source. Neither snapshot implies automatic updates.

Remaining work: incremental PostgreSQL synchronization, scheduled refreshes, municipal coverage,
verified historical corporate groups, newer gas network evidence, and
clarification of some distribution sources' terms before redistributing the
complete dataset, including the historical gas-network annex.

Update this guide when contracts or instructions change. Keep operational
details in `docs` rather than accumulating session transcripts here.
