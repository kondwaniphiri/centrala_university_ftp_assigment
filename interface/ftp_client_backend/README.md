# FTP Client Backend Extensions

This backend (Flask) now supports bulk downloading of MED_DATA CSV files from the Node.js FTP server, validating them, and storing them in a dated folder structure while logging activity and errors.

## Key Features
- Session-based FTP operations (connect, list, cwd, upload, download)
- New endpoints for data workflow:
  - `POST /api/list-files` – List CSV files with pattern match + downloaded flag
  - `POST /api/bulk-download` – Download & validate multiple CSVs in one request
  - `POST /api/new-files` – Identify CSVs not yet downloaded/validated
  - Existing `GET /api/download` retained for single raw download
- Validation performed by `validate_csv.py` implementing assignment rules.
- Valid files stored under `downloads/YYYY-MM/` with original filename.
- Tracking file `logs/downloaded_files.txt` prevents duplicate re-processing.
- Structured log `logs/download_log.json` appends metadata per successful file.
- Error log `logs/validation_errors.log` lines contain: timestamp, GUID (from external UUID API fallback local), filename, issues.

## Validation Rules
1. Filename pattern: `MED_DATA_YYYYMMDDHHMMSS.csv`
2. Headers exact: `batch_id,timestamp,reading1..reading10`
3. No duplicate `batch_id` entries inside the same file
4. Row must have 12 columns total
5. Readings: float, 0 <= value < 9.9
6. Not empty, at least one data row
7. Must parse (CSV format); malformed lines flagged

## Endpoints Detail

### POST /api/list-files
Request: `{ "token": "..." }`
Response:
```
{ "files": [ { "name": "MED_DATA_...csv", "matches_pattern": true, "downloaded": false }, ... ] }
```

### POST /api/bulk-download
Request:
```
{
  "token": "<session>",
  "files": ["MED_DATA_20230603140104.csv", "MED_DATA_20230603140105.csv"],
  "skipDownloaded": true
}
```
Response:
```
{
  "results": [
    {"name":"MED_DATA_...04.csv","valid":true,"rows":10,"issues":[],"stored_path":"2025-09/MED_DATA_...04.csv"},
    {"name":"MED_DATA_...05.csv","valid":false,"issues":["duplicate_batch_id"],"error_guid":"..."}
  ]
}
```

### POST /api/new-files
Request: `{ "token": "..." }`
Response: `{ "new": ["MED_DATA_...csv", ...] }`

## Front-End Integration
The web client now displays a CSV file table with selection checkboxes. Already downloaded files are disabled. Buttons:
- Bulk Download + Validate
- Check New Files
Result JSON is rendered into a textarea for inspection / copy.

## Error GUIDs
Each invalid file log entry obtains a UUID v1 from `https://www.uuidtools.com/api/generate/v1`. If the API call fails (offline, rate limit), a locally generated `uuid.uuid1()` value is used instead.

## Developer Notes
- Extend validation rules or logs by editing `validate_csv.py` or the logging helpers in `app.py`.
- Download/validation is atomic per file; a failure in one does not halt the batch.
- The tracking list is line-based and simple; for higher scale consider a SQLite DB.

## Future Enhancements (Ideas)
- Pagination & size metadata for remote files.
- Integrity hash (SHA256) manifest generation for each valid file.
- Retry queue for transient FTP/network issues.
- Export aggregated summary metrics endpoint.

## Running
Ensure Python dependencies installed (Flask, flask-cors). Run backend:
```
python app.py
```
Open `interface/web_client/index.html` in a browser (or serve statically) and connect to the FTP server.
