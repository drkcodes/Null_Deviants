SKYGUARDAI FINAL UPDATE
========================

This package contains the cleaned frontend source and the historical telemetry seeding script.

1. FRONTEND
-----------
Copy/replace the CONTENTS of this package's aws_prototype folder into:
  C:\Users\dilee\Desktop\Null_Deviants\aws_prototype

Do NOT copy node_modules from anywhere. Keep your existing Windows node_modules.

The included .env.local points to:
  http://127.0.0.1:8000

2. BACKEND HISTORY
------------------
Copy:
  BACKEND\seed_history.py
into:
  C:\Users\dilee\Desktop\Null_Deviants\BACKEND\seed_history.py

Then, in a PowerShell terminal:
  cd "C:\Users\dilee\Desktop\Null_Deviants\BACKEND"
  .\.venv\Scripts\activate
  python seed_history.py

This ADDS seven days of real benchmark telemetry (15-minute observations) for every station.
It does NOT delete the existing ML anomaly records.

3. START SERVERS
----------------
Backend:
  cd "C:\Users\dilee\Desktop\Null_Deviants\BACKEND"
  .\.venv\Scripts\activate
  python -m uvicorn main:app --host 127.0.0.1 --port 8000

Frontend (separate terminal):
  cd "C:\Users\dilee\Desktop\Null_Deviants\aws_prototype"
  npm run dev

Open:
  http://localhost:3000

4. IMPORTANT
------------
Do not run npm install again unless your existing frontend dependencies are missing.
Do not run npm audit fix for the demo.
Do not delete weatherguard.db before running seed_history.py.

The final frontend contains no operational MOCK_* data, no Render backend fallback,
and uses SkyGuardAI branding.
