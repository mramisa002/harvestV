# HarvestV frontend — connected to FastAPI

This is the complete original Next.js frontend from Harvest-V-main.zip, including
the supplied screens, images, fonts and design styles.

Follow **../START_HERE.md** to start both servers on Windows. Connection details
and the screen-to-endpoint mapping are in **INTEGRATION.md**.

```powershell
npm ci
Copy-Item .env.local.example .env.local
npm run dev
```

Open http://127.0.0.1:3000 and keep the backend running at port 8000.

Farm profiles, text feedback and saved advisory snapshots persist on the server
under an anonymous browser token. Dashboard and Crop Rotation include connected
district/crop advisory panels with real API loading, error and freshness states.

The three-season crop rotation cards and financial figures are still labelled
design examples. The API currently supplies experimental sowing windows for
wheat, mustard, lentil and potato; it does not optimize three-season rotations.
Photo uploads, expert replies, account login, source retrieval and live farm
mapping remain outside this implementation.

Checks after installing dependencies:

```powershell
npm run typecheck
npm run build
npm run test:api
```

The Figma generator scripts are retained for reference. They predate the manual
backend integration: running them can overwrite inserted advisory panels, so
compare and preserve those changes if regenerating design components.

ORIGINAL_README.md preserves the documentation of the earlier frontend-only
version for reference. It does not describe the current connected behavior.
