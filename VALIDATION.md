# Verification record

Verified on 12 November 2026 using the available Python 3.14 environment.
The deployment target is Python 3.12 as declared in the Dockerfile.

- 36 offline unittest cases pass: scoring boundaries, observed vetoes,
  freshness/gaps, unknown soil estimates, root/surface freshness separation,
  20-year-history requirement, future-observation exclusion, Bangla templates,
  provider-schema parsing, source unit validation, 64-district catalog,
  cache idempotency, API handlers, response schema, OpenAPI and CORS configuration.
- Additional persistence checks cover farm updates, browser-token isolation,
  feedback idempotency, payload validation, server-calculated saved advisories,
  and the explicit UNVERIFIED information-check response.
- Python source compiles.
- The synthetic backtest demonstration generates CSV and Markdown output.
- Project manifests and Compose YAML parse; frontend manifest matches its lockfile.
- Diagnostic frontend JavaScript passes a syntax check.
- All 21 frontend TypeScript/TSX files pass a compiler syntax check (TypeScript 6.0.3).
- Five API-client tests check URL/header handling, stable device tokens, farm
  request bodies, bilingual backend errors, connection failures and cancellation.

Not verified here:

- Actual HTTP serving/browser interactions: the sandbox blocks the loopback
  socket used by the test client's event loop. Tests call handlers directly;
  they do not establish HTTP transport behavior.
- Live NASA POWER requests or authenticated Earthdata downloads/extraction:
  network DNS was unavailable and Earthdata credentials were not supplied.
- PostgreSQL, Docker and Python 3.12 execution: unavailable in this environment.
- Next.js production build and browser tests: complete source is now present,
  but npm dependency downloads failed because network DNS was unavailable.
- Agricultural accuracy, Bangla review or actual satellite-derived NDVI metrics.

Fixtures and the sample backtest are synthetic, not recorded NASA observations.
Product-specific Earthdata QA/reprojection pipelines and their scheduling still
need completion with real source granules. See README.md for scope and setup.
