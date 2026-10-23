# Centrala University FTP CSV Validation System

**Author:** Kondwani Phiri

**Student Identification Number:** 21163650

**Assignment:** ATHE Level 4 Unit 11 Advanced Programming

A local demonstration that generates pharmaceutical trial CSV samples, hosts them
on an FTP server, and lets users download and validate them through a browser.
All sample records are synthetic.

## Project structure

| Path | Purpose |
| --- | --- |
| `FTP_server/server.js` | Node.js FTP service using `ftp-srv` |
| `FTP_server/generate_csv_data.py` | Seeded valid and invalid CSV generator |
| `FTP_server/ftp-roots/default/` | Sample CSVs and generation descriptors |
| `interface/ftp_client_backend/app.py` | Flask API and FTP session management |
| `interface/ftp_client_backend/validate_csv.py` | Shared CSV validation logic |
| `interface/web_client/` | HTML, CSS and JavaScript interface |
| `tests/` | Python and frontend regression tests |
| `output/evidence/` | Captured test results, API results and log snapshots |
| `Report.docx` | Updated report with screenshots and assessment limitations |
| `reset_state.py` | Clear locally generated download state |

## Setup and run

Requirements: Python 3.11 or later, Node.js 18 or later, and npm.

From the project root, install dependencies:

```powershell
python -m pip install -r interface/ftp_client_backend/requirements.txt
npm ci --prefix FTP_server
```

Run the services in separate terminals:

```powershell
node FTP_server/server.js
```

```powershell
python interface/ftp_client_backend/app.py
```

Open `interface/web_client/index.html` in a browser. Connect using:

| Setting | Demo value |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `2121` |
| User | `user` |
| Password | `pass` |

Refresh the listing, select CSV files, then click **Download**. The interface
reports accepted, invalid, skipped and failed files. Selection persists across
pages. Successfully processed files and previously invalid files are hidden from
subsequent listings.

Windows helper scripts are also provided in `FTP_server/` and `interface/`.
Both services bind to localhost; Flask debug mode is disabled. FTP is unencrypted
and this setup is intended for a local assignment demonstration.

## Generate sample records

```powershell
python FTP_server/generate_csv_data.py --total 30 --valid-ratio 0.7 --seed 42 --verify
```

The generator writes to the FTP root and resumes after existing conventional
filenames and batch IDs. `--count` is an alias for `--total`. Output directories
are created automatically. `--no-resume` requires a directory without CSV files
to prevent accidental overwrites.

The recorded demonstration generated **30 files: 21 valid and 9 intentionally
invalid**, with 279 generated data rows. The generator and shared validator
agreed on all 30 files. Screenshots are embedded in `Report.docx`.

## Validation and storage

- Require `MED_DATA_YYYYMMDDHHMMSS.csv` and a real calendar date and time.
- Require the exact headers `batch_id,timestamp,reading1` through `reading10`.
- Require 12 columns per row, integer batch IDs, and valid `HH:MM:SS` timestamps.
- Reject duplicate batch IDs within a file.
- Require finite numeric readings satisfying `0 <= value < 9.9`.
- Reject empty files, files without data rows, and malformed CSV quoting.

Candidates are validated in isolated staging directories before acceptance.
Ordinary CSV names that break the naming convention are logged without being
downloaded. Unsafe path-like names are rejected before any FTP or local write.

At runtime, accepted files are stored under
`interface/ftp_client_backend/downloads/YYYY-MM/` and mirrored under
`interface/web_client/downloads/YYYY-MM/`. The folder uses the UTC processing
month. The backend creates these directories and its logs automatically.

Successful filenames are tracked in `logs/downloaded_files.txt`; metadata is
stored in `logs/download_log.json`. Invalid entries are recorded in
`logs/validation_errors.log`, with a timestamp, GUID, filename and issue codes.
The logger attempts an external UUID API and falls back to a local UUID.

Runtime logs, downloads, dependency folders, process IDs and caches are ignored
by Git. Historical demonstration snapshots remain in `output/evidence/`.

## Tests and continuous integration

```powershell
python -m pip install pytest
python -m pytest -q
node --test tests/test_web_client.cjs
```

The verified local run passed **33 Python tests and 3 frontend tests**. Python
reported deprecation warnings for `datetime.utcnow`; coverage was not measured.
The captured outputs are in `output/evidence/`.

GitHub Actions runs Python tests, frontend tests, FTP checks and artifact
packaging on pushes and pull requests. The workflow does not deploy an
application. A successful remote run must be checked separately.

## Reset local demonstration state

```powershell
python reset_state.py --all
```

This removes local logs and downloaded copies so the samples can be processed
again. It preserves source CSVs in the FTP root. Stop the services before using
the reset script.

The API alternative is `POST /api/reset-state` with an active session token:

```json
{"token": "<session>", "purgeDownloads": true}
```

## Assignment limitations

The report distinguishes verified functionality from remaining work. Date search
defaulting to today, container deployment, verified remote CI results, and
historical test-first evidence are not established by the local demonstration.
The code does not implement the optional Strategy design pattern extension.

The validator currently excludes exactly `9.9`, although the brief describes
values not exceeding `9.9`. The generator uses up to three decimal places, but
the validator does not enforce decimal precision. Resolve these interpretations
against the marking requirements before claiming full conformance.

Duplicate suppression uses filenames rather than content hashes. The API has an
explicit `skipDownloaded` option. State uses separate text and JSON writes and
is intended for one backend process, not a production medical-data deployment.
