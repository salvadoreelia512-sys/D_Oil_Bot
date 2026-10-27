# CL Quant: Windows-generated standalone package

This package was generated locally using the PowerShell script.
It is a compact standalone version, not the inaccessible original ZIP.

## Run on Windows

Install Python 3.12 from python.org and enable "Add Python to PATH".
Open PowerShell in this folder, then run:

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m unittest test_engine.py
    .\.venv\Scripts\python.exe -m streamlit run app.py

No PowerShell activation or execution-policy changes are needed.

Synthetic demo works without API access after dependencies are installed.
Public mode uses Yahoo, FRED and public EIA spreadsheets without API keys.
Missing freight or curve observations cause HOLD; they are not invented.

The included tests check selected implementation behavior.
This Windows-generated version has not been executed in the unavailable coding
environment. No inherited test-pass count or predictive accuracy claim is made.

## GitHub upload

Create a new empty public repository.
Upload the CONTENTS of this folder, not the ZIP.
app.py and requirements.txt must be at the repository's top level.
Include data.py, engine.py, test_engine.py and the .streamlit folder.

Alternatively, with Git installed, run from this folder:

    git init -b main
    git add .
    git commit -m "Add free CL research application"
    git remote add origin https://github.com/YOUR_USERNAME/cl-quant.git
    git push -u origin main

Create the empty repository first and replace YOUR_USERNAME.

## Free Streamlit deployment

Go to https://share.streamlit.io/
Connect the public GitHub repository.
Select branch main, app.py and Python 3.12.
Leave secrets empty and deploy using Community Cloud.

There are no paid APIs, broker connections, LLM services, databases or GPU services.
Do not opt into paid hosting or add-ons.

Free cloud plans and public feeds may change, sleep or become unavailable.
Perpetual free cloud uptime and exchange-quality live data cannot be guaranteed.
The local application and synthetic mode remain the zero-charge fallback.

## Research limitations

Read MATHEMATICS.md.
Coefficients and event assumptions are unvalidated.
Yahoo CL=F is a rolling contract proxy and may be delayed.
Capacity is assumed until verified. EIA dates are reporting periods.
No profitable strategy, calibrated recommendation or exact fill is promised.