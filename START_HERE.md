# Run HarvestV on your Windows laptop

This package now includes your **complete original frontend**, its images and
styles, and the connected FastAPI backend. Extract the ZIP before running it.

## 1. Open the folder

In VS Code, choose **File → Open Folder → HarvestV**. Choose **Terminal → New
Terminal**. Keep two terminal tabs open: one for the backend and one for the
frontend.

## 2. Backend — first terminal

Install Python 3.12 if you do not have it. Run:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave this terminal running. API documentation: http://127.0.0.1:8000/docs.
The database and all required tables are created automatically on startup.

## 3. Frontend — second terminal

Install Node.js 20.9 or newer if you do not have it. From the HarvestV root:

```powershell
cd frontend
npm ci
Copy-Item .env.local.example .env.local
npm run dev
```

Open **http://127.0.0.1:3000**. Use that same address each time: localhost and
127.0.0.1 have separate browser storage. Press **Ctrl+C** in each terminal to stop.

## 4. Try the connected features

1. Go to **My Farm**, choose your actual district in the new district selector,
   edit the original form, and click **Save Farm**. A message confirms that the
   server stored it. Reload to confirm it returns.
2. Go to **Crop Rotation** or **Dashboard**. The advisory panel reads the saved
   district, fetches the four supported crops and requests cached conditions.
3. Submit text through **Feedback**. It is stored by the backend and appears in
   the server-saved list. Photos are still local selections; expert replies are
   not connected.
4. On **Information Check**, the server explicitly returns **UNVERIFIED** because
   evidence retrieval is not implemented. It will not invent citations.

## 5. Load NASA observations for advice

The UI is connected immediately. A new database has no weather history, so it
will correctly show a missing-data message rather than a made-up result.
Open a third terminal from the project root and run:

```powershell
cd backend
.venv\Scripts\python -m app.ingestion power --district chattogram --years 20
```

Choose the same district in the website, or replace `chattogram` with your
district slug from the API's `/api/v1/districts` list. Initial history ingestion
can take time. Run without `--years 20` for daily refreshes. Click **Refresh** in
the advisory panel after ingestion finishes.

Advice is experimental. Missing soil measurements lower confidence. The original
three-season rotation cards, dashboard design figures, soil map and research
cards remain marked examples; they are not results from this sowing-window API.
Do not use those example figures as validated farming instructions.

## If it does not connect

- Keep both terminal processes running.
- Backend URL: `http://127.0.0.1:8000`; website URL: `http://127.0.0.1:3000`.
- Frontend `.env.local` must contain `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.
  Restart the frontend after changing it.
- CORS origins in `backend/.env` must include the exact website origin.
- Missing/stale NASA data is different from a failed server connection; the UI
  displays the backend's error message.

Your browser holds an anonymous device token for its server-saved farm, feedback
and advisories. Clearing the site's browser data loses access to those records.
There is no account login or cross-device sync. Do not share that token.
