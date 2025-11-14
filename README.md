Author: Kondwani Phiri
SIN: 21163650

# FTP CSV Validation Demo

End-to-end demo environment for generating CSV files over a local FTP server, downloading & validating them via a Flask backend, and interacting through a simple web client.

## Assignment Objectives & Alignment

Below each inferred Unit 11 Advanced Programming objective is mapped to implemented elements. (If the official wording differs, replace the left column text only—code references remain valid.)

| Objective (Inferred)                                              | Implementation Evidence                                                                                                                                                                                                                                                                 |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Design & implement a modular multi-component software solution | Clear separation of concerns: generator (`FTP_server/generate_csv_data.py`), transport (`FTP_server/server.js`), backend API (`interface/ftp_client_backend/app.py`), validation logic (`validate_csv.py`), UI (`interface/web_client/*`), utilities (batch scripts, `reset_state.py`). |
| 2. Handle data acquisition, transformation & validation robustly  | Post-download validation pipeline with granular issue codes; resume-aware generator producing both valid & intentionally invalid datasets.                                                                                                                                              |
| 3. Implement persistent state & logging                           | File-based logs: `validation_errors.log`, `download_log.json`, `downloaded_files.txt`; stored validated CSVs under dated subfolders; mirrored web downloads directory.                                                                                                                  |
| 4. Provide a user-facing interface supporting core workflows      | Lightweight HTML/JS client with pagination, selection persistence, activity/status feedback, natural language validation summaries.                                                                                                                                                     |
| 5. Demonstrate error handling & resilience                        | Try/except wrapping FTP operations, graceful skips for previously invalid / already downloaded files, safe resume logic, defensive parsing in validator.                                                                                                                                |
| 6. Apply scripting / automation to streamline operations          | Batch scripts for starting/stopping services (`start_ftp.bat`, `stop_ftp.bat`, `start_app.bat`, `stop_app.bat`, `run_generator.bat`), plus `reset_state.py` for environment resets.                                                                                                     |
| 7. Support extensibility & maintainable code practices            | Docstrings & comments added across major modules; dataclasses (`ValidationResult`, `FileDescriptor`); constants centralized; modular function boundaries.                                                                                                                               |
| 8. Address security & ethical considerations (introductory level) | Filename pattern enforcement limits arbitrary file handling; segregation of invalid data; explicit listing suppression. (Not yet implemented: credential hashing, TLS, API auth).                                                                                                       |
| 9. Plan for testing & quality assurance                           | Generator `--verify` mode cross-checks rule parity; proposed unit test matrix documented in `Assignment_Report.xml` (Appendix D).                                                                                                                                                       |
| 10. Provide comprehensive technical documentation & evaluation    | This README + `Assignment_Report.xml` deliver architectural, operational, and evaluative documentation; inline comments clarify logic.                                                                                                                                                  |
| 11. Demonstrate iterative improvement & problem solving           | History of refinements: invalid suppression, filename bug fix (temp prefix removal), resume logic addition, selection pruning, reset endpoint.                                                                                                                                          |

onents

| Path                            | Description                                                                                      |
| ------------------------------- | ------------------------------------------------------------------------------------------------ |
| `FTP_server/`                   | Node-based local FTP server (`server.js`) plus CSV generator & helper batch scripts.             |
| `interface/ftp_client_backend/` | Flask backend API (`app.py`) that connects to FTP, lists, downloads, validates and logs results. |
| `interface/web_client/`         | Static HTML/JS client (`index.html`, `app.js`) to drive the workflow.                            |
| `csv_generator/`                | Original standalone CSV generator variant (optional / experimental).                             |
| `reset_state.py`                | Utility script to clear validation / download state.                                             |
| `README.md`                     | This file.                                                                                       |

## Features (Concise)

- Local FTP server (user: `user`, password: `pass`, default port: `2121`).
- CSV file generation with a mix of valid and intentionally invalid files.
- Resume-capable generator (in `FTP_server/generate_csv_data.py`) continuing timestamps & batch IDs without collisions.
- Flask backend endpoints for connect, list filtered CSVs, bulk download + validation, new-file polling, and state reset.
- Automatic suppression of previously invalid or already-downloaded files from listings.
- Front-end with pagination, multi-page selection persistence, sentence-form validation summaries, activity/status bar.
- Reset endpoint & script to clear logs and downloaded artifacts.

## Requirements

### System

- Windows (batch scripts provided) – should also work on other platforms manually (Node + Python commands).

### Software

| Tool    | Version (tested)                              |
| ------- | --------------------------------------------- |
| Python  | 3.11+ (validator/back-end uses modern syntax) |
| Node.js | 18+                                           |
| npm     | (bundled with Node)                           |

### Python Dependencies

Defined in `interface/ftp_client_backend/requirements.txt`:

```
Flask==3.0.3
flask-cors==4.0.0
```

Install (from repo root or from `interface/ftp_client_backend`):

```
pip install -r interface/ftp_client_backend/requirements.txt
```

### Node Dependencies

Inside `FTP_server/`:

```
npm install
```

This installs `ftp-srv` (only runtime dependency).

## Quick Start (Most Common Workflow)

1. Install dependencies (one time):
   - Python libs: `pip install -r interface/ftp_client_backend/requirements.txt`
   - Node deps: `cd FTP_server && npm install && cd ..`
2. Start the FTP server:
   - `FTP_server\start_ftp.bat`
3. Start the Flask backend:
   - `interface\start_app.bat`
4. Open the web UI:
   - Open `interface\web_client\index.html` in your browser (double-click or drag into a tab).
5. Connect using the form:
   - Host: `127.0.0.1`
   - Port: `2121`
   - User: `user`
   - Password: `pass`
6. Generate more CSV files anytime:
   - `FTP_server\run_generator.bat --count 25`
     (Optional flags: `--no-resume` to force a fresh sequence; see generator's help with `-h`.)
7. Click Refresh in the UI, select files, then Download to validate.
8. Use the results pane & summary for validation outcomes.
9. To reset state (clear logs & downloaded files):
   - Script: `python reset_state.py`
   - Or API: POST `/api/reset-state` (optionally `{ "purgeDownloads": true }`).
10. Stop services when done:

- Flask: `interface\stop_app.bat`
- FTP: `FTP_server\stop_ftp.bat`

## Batch Scripts Overview

| Script                         | Location   | Purpose                                                  |
| ------------------------------ | ---------- | -------------------------------------------------------- |
| `interface\start_app.bat`      | interface  | Start Flask backend (records PID).                       |
| `interface\stop_app.bat`       | interface  | Stop Flask backend using PID file.                       |
| `FTP_server\start_ftp.bat`     | FTP_server | Start Node FTP server (`server.js`).                     |
| `FTP_server\stop_ftp.bat`      | FTP_server | Stop FTP server via PID file.                            |
| `FTP_server\run_generator.bat` | FTP_server | Run CSV generator; supports passing arguments.           |
| `interface\run_servers.bat`    | interface  | (Earlier variant) Start FTP + Flask together (optional). |

## Generator (FTP_server/generate_csv_data.py)

Key options (run with `python generate_csv_data.py -h` for full list):

- `--count N` : Number of files to generate (default 10).
- `--valid-ratio R` : Approximate fraction of valid files (0–1).
- `--no-resume` : Disable resume logic; start from current UTC time + sequential IDs.
- `--verify` : (If implemented) Run internal validation alignment checks.

Outputs:

- CSV files placed in `FTP_server/ftp-roots/default/` so they are immediately visible over FTP.
- Generation logs in `FTP_server/generation_logs/`.

## Validation Rules (Summary)

A file is valid if:

1. Filename matches: `MED_DATA_YYYYMMDDHHMMSS.csv`
2. Header matches the expected static header (see `validate_csv.py`).
3. Each data row has the correct number/order of columns.
4. Numeric ranges fall within allowed bounds (e.g., `< 9.9` per current logic).
5. No duplicate batch IDs inside the same file.
6. File is not empty and parses cleanly as CSV.

Invalid files are logged to: `interface/ftp_client_backend/logs/validation_errors.log`.
Previously invalid files are suppressed from the UI list automatically.

## Logs & State Tracking

| File                                                      | Purpose                                                                        |
| --------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `interface/ftp_client_backend/logs/download_log.json`     | Records metadata about valid downloaded files.                                 |
| `interface/ftp_client_backend/logs/downloaded_files.txt`  | Set-like list of validated filenames (used for suppression).                   |
| `interface/ftp_client_backend/logs/validation_errors.log` | Lines describing invalid file occurrences (timestamp, UUID, filename, issues). |
| `interface/ftp_client_backend/downloads/YYYY-MM/`         | Stored validated CSVs.                                                         |
| `interface/web_client/downloads/YYYY-MM/`                 | Mirror for front-end access / demonstration.                                   |

## Resetting State

Use `python reset_state.py` to remove logs and (optionally, if configured in script) downloaded artifacts, or call the backend endpoint:

```
POST http://127.0.0.1:5000/api/reset-state
Body: { "purgeDownloads": true }
```

## Troubleshooting

- Port already in use (2121): Stop any previous FTP server window/process; or change `PORT` in `server.js`.
- Flask not starting: Ensure dependencies installed; run directly with `python interface/ftp_client_backend/app.py` to see errors.
- No files listed: Generate more CSVs with the generator; ensure they have `.csv` extension; invalid or already-downloaded files are automatically hidden.
- Stuck invalid suppression after reset: Confirm you deleted all three: `validation_errors.log`, `download_log.json`, `downloaded_files.txt` and refreshed the UI.

## Optional Enhancements (Future Ideas)

- Add a small dashboard page to inspect invalid file history.
- Toggle to show/hide previously processed files.
- Containerize with Docker Compose for single-command startup.
- Add automated tests for validator logic.

## License

Internal/demo use only (no explicit license set).

---

Feel free to substitute official objective language once inserted; implementation evidence rows will remain accurate.
