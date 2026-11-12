# Frontend/backend integration

The original Next.js App Router pages, Figma assets, fonts and CSS are included.
The existing forms and navigation remain in place.

| Screen | Connected behavior |
| --- | --- |
| My Farm | Loads district catalog and server-saved profile; saves text/radio/soil fields with PUT `/api/v1/farm` |
| Crop Rotation | Fetches supported crops and GET `/api/v1/advisory`; loads recent observations; saves authoritative server-generated advisory snapshots |
| Dashboard | Same district/crop advisory panel plus GET `/api/v1/saved-advisories` |
| Feedback | POST text observations with idempotency UUIDs; GET server-saved feedback |
| Information Check | POST request returns explicit UNVERIFIED, without fabricated sources |

`src/lib/backend.ts` contains the typed API client, request cancellation,
20-second timeouts, network/HTTP error handling and the browser-scoped bearer
token. `src/lib/harvestv-api.ts` re-exports it for compatibility.

`src/components/advisory-panel.tsx` renders the response and data freshness,
including null windows and missing-data errors. Switching language refetches
localized advice; old requests are aborted so earlier responses cannot overwrite
a newer district/crop selection. Refresh fetches the catalogs and current data.

`src/components/page-interactions.tsx` wires the original farm, feedback and
information-check buttons. Radio inputs are read only when checked; loading a
saved profile does not overwrite radio `value` attributes. Existing browser-only
profiles are not silently uploaded: the user must save the form.
Self-reported soil-test fields are stored as profile information; they do not
silently replace reviewed district soil parameters in the advisory model.

`src/app/connected.css` styles the connected panels alongside the original theme.
Original example cards are explicitly labelled. Their plan-saving buttons direct
users to the connected advisory panel instead of treating sample cards as real
server recommendations.

## Start

Follow `../START_HERE.md`. The API URL is public configuration, not a credential.
Never add Earthdata tokens or database passwords to a NEXT_PUBLIC variable.

## Still outside this implementation

- Authentication/accounts, cross-device profile sync and expert replies.
- Photo upload and analysis, live map boundaries, evidence/source retrieval.
- Three-season rotation optimization, profit predictions or fertilizer schedules.
- Forecast provider and fully verified Earthdata processing pipelines.

These are not implied by a connected API. The backend currently computes
experimental district-level sowing-window advice for four Rabi crops.
