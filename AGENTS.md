# Project guide for agents

## Scope

A public map of Spain, including the islands, Ceuta and Melilla, for exploring
electricity distributors, retailers and market trends. Gas is planned: retain
the `sector` field without implementing it yet. Prices, offers, personal data
and SIPS are out of scope.

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
- `packages/ingestion`: batch CNMC Data ingestion and refresh.
- `packages/map_pipeline`: cartographic preparation and PMTiles.
- `scripts`: database initialization, migration and export.
- `docs`: operating instructions and data rules.

Organize React by feature (`map`, `market`, `distribution`, `legal`), adding
`pages`, `layouts`, `components`, `hooks`, `actions`, `interfaces`, `lib`
and `store` only as needed. Keep page-specific UI in `pages/<page>/ui`.
Shared code belongs in `src/api`, `src/components`, `src/interfaces` and
`src/lib`; keep `main.tsx` and `app.router.tsx` in `src`.
Do not create empty directories. Components and hooks use `.tsx`; utilities
without JSX use `.ts`.

## Contracts

- A distributor (R1, distribuidora) operates the physical network; a retailer
  (R2, comercializadora) sells energy. Multiple distributors can coexist in
  one municipality.
- Market data is national or regional. Do not infer provincial or municipal
  coverage or consolidate companies without evidence.
- Distribution publishes only accepted positive claims with a source, date
  and confidence level. `complete=false` with an empty list means unknown.
  Provincial colors do not delineate the network and are hidden at municipal zoom.
- Reference retailers (COR) have an independent catalogue. Do not automatically
  associate them with distributors or invent exclusivity. Corporate affiliation
  and geographic presence require independent evidence.
- Preserve leading zeros in INE codes, exact joins by code, and the layers
  `municipios`, `provincias`, `ccaa` and `unidades_auxiliares`. Use dated
  current boundaries without presenting them as historical boundaries.
  Keep one point label per territory.
- URLs preserve filters and history within `/`, `/evolution` and
  `/regulated-tariff`; navigation between pages starts without the previous
  page's filters.
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
local SQLite (`ENV=development`, `MAPA_DATABASE`) or remote Turso
(`ENV=production`, URL and read-only token). Production has no local fallback.
Do not create tables or run migrations at API startup. Local refreshes are
transactional; the remote uploader initializes empty databases only and does
not perform incremental synchronization.

Use mapped SQLAlchemy models and `select()` expressions for API service queries,
including distribution. Do not use `text()` for those reads. Database setup and
ingestion retain their schema SQL and SQLite-specific transactional operations.

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
with an empty `VITE_API_BASE_URL`. The private Turso connection token is separate
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
The previous data snapshot contains 60 quarters (2011T1–2025T4), 1,426,773 rows
and evidence for 48 of 52 provinces. Codes `09`, `12`, `35` and `47`
remain unknown. This does not imply automatic updates.

Remaining work: incremental Turso synchronization, scheduled refreshes,
municipal coverage, verified historical corporate groups, and clarification
of some distribution sources' terms before redistributing the complete dataset.

Update this guide when contracts or instructions change. Keep operational
details in `docs` rather than accumulating session transcripts here.
