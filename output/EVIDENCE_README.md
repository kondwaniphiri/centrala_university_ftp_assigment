# Assignment evidence

Author: Kondwani Phiri

The project report is [`../Report.docx`](../Report.docx). It contains the captured
screenshots of the local FTP workflow, generated data, tests, storage, error logs
and API checks, together with explanations and remaining assignment limitations.

The `evidence/` directory preserves actual demonstration outputs:

| File | Contents |
| --- | --- |
| `python_tests.txt` | 33 passing Python regression tests |
| `frontend_tests.txt` | 3 passing frontend regression tests |
| `results.json` | Live health, duplicate-download and unsafe-path checks; generation totals |
| `ui_results.txt` | Initial bulk download output, before the filename logging correction described in the report |
| `download_log.json` | Snapshot of successful download metadata |
| `validation_errors.txt` | Snapshot of rejected-file logs, including the corrected filename rejection |

The new generation batch contained 30 CSV files: 21 valid and 9 intentionally
invalid, with 279 generated data rows. Source records are retained under
`../FTP_server/ftp-roots/default/`, alongside generation descriptors.

Downloaded mirrors and live tracking logs are recreated when the application
runs. They are excluded from the repository so a fresh checkout can process the
sample files. Temporary report-building tools, cached dependencies and process
IDs were removed during repository cleanup.
