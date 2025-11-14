"""CSV Test Data Generator

Generates a mixture of valid and intentionally invalid MED_DATA CSV files.

Invalid conditions we optionally inject:
    1. Incorrect filename format
    2. Duplicate batch_id within file
    3. Missing or misspelled headers
    4. Missing columns in one or more rows
    5. Reading value >= 9.9 (out of accepted range)
    6. Empty (0‑byte) file
    7. Malformed CSV line (unbalanced quote)

Resume Logic Overview:
    * Before producing new files we scan the output directory for the latest
        MED_DATA_ timestamp and existing batch_ids. We then start one second after
        the newest timestamp and jump batch_ids forward by +10 from the current
        maximum to avoid collisions with in‑flight / partially processed data.

Validity Ratio Enforcement:
    * We target (valid_ratio) proportion of valid files. Instead of choosing
        validity blindly we look at what remains to be produced and bias the
        decision so the final distribution stays near the requested ratio without
        large drift.

Outputs:
    * CSV files directly into the FTP server root (ftp-roots/default) so they
        are immediately listable.
    * generation_log.json + generation_errors.log inside a central
        generation_logs/ directory (sibling to FTP_server) for quick inspection.

Usage (PowerShell example):
        python generate_csv_data.py --total 50 --valid-ratio 0.75 --seed 42
        python generate_csv_data.py --total 25 --no-resume
"""
from __future__ import annotations
import argparse
import csv
import json
import random
from dataclasses import dataclass, asdict
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Iterable, Optional

VALID_HEADERS = [
    "batch_id","timestamp",
    *[f"reading{i}" for i in range(1,11)]
]

HEADER_VARIANTS = [
    ["batch","timestamp", *[f"reading{i}" for i in range(1,11)]],  # misspelled batch_id
    VALID_HEADERS[:-1],  
    [h.upper() for h in VALID_HEADERS],  # unexpected casing
]

@dataclass
class FileDescriptor:
    filename: str
    is_valid: bool
    issues: List[str]
    record_count: int
    batch_ids: List[int]

RANDOM_TS_BASE = datetime(2024,6,3,14,1,4)

FILENAME_PATTERN = 'MED_DATA_%Y%m%d%H%M%S.csv'

def parse_existing_timestamp(filename: str) -> Optional[datetime]:
    """Extract a datetime from a MED_DATA_*.csv filename or return None.
    Safe helper used during resume scanning—any failure simply returns None.
    """
    if not (filename.startswith('MED_DATA_') and filename.endswith('.csv')):
        return None
    core = filename[len('MED_DATA_'):-4]
    if len(core) != 14 or not core.isdigit():
        return None
    try:
        return datetime.strptime(core, '%Y%m%d%H%M%S')
    except Exception:
        return None

def scan_existing(out_dir: Path) -> tuple[Optional[datetime], set[int]]:
    """Scan existing output for:
    * latest timestamp among MED_DATA_* files
    * set of all batch_ids encountered

    This allows the generator (when resume=True) to continue seamlessly
    without overwriting or reusing identifiers.
    Any per‑file read/parse errors are ignored for resilience.
    """
    latest: Optional[datetime] = None
    batch_ids: set[int] = set()
    if not out_dir.exists():
        return None, batch_ids
    for p in out_dir.glob('MED_DATA_*.csv'):
        ts = parse_existing_timestamp(p.name)
        if ts and (latest is None or ts > latest):
            latest = ts
        try:
            with p.open('r', encoding='utf-8', newline='') as f:
                import csv as _csv
                r = _csv.reader(f)
                headers = next(r, None)
                for row in r:
                    if not row:
                        continue
                    try:
                        bid = int(row[0])
                        batch_ids.add(bid)
                    except Exception:
                        continue
        except Exception:
            continue
    return latest, batch_ids


def generate_valid_row(batch_id: int, timestamp: datetime) -> List[Any]:
    # Generate 10 readings each < 9.9 with up to 3 decimal places
    readings = [round(random.uniform(0,9.899), 3) for _ in range(10)]
    return [batch_id, timestamp.strftime("%H:%M:%S"), *readings]


def random_filename(dt: datetime) -> str:
    return f"MED_DATA_{dt.strftime('%Y%m%d%H%M%S')}.csv"


def corrupt_filename(base_name: str) -> str:
    variants = [
        base_name.replace("MED_DATA_", "MEDDATA_"),
        base_name.replace(".csv", ".CSV"),
        base_name.lower(),
        base_name.replace("2025", "23"),
        base_name.replace("MED_DATA_", "MED-DATA-"),
    ]
    return random.choice(variants)


def inject_duplicate_batch(rows: List[List[Any]]) -> List[str]:
    if not rows:
        return ["duplicate_batch_id_failed_empty"]
    # Duplicate first row's batch id into another row
    dup_id = rows[0][0]
    target_index = random.randrange(len(rows))
    rows[target_index][0] = dup_id
    return ["duplicate_batch_id"]


def inject_missing_columns(rows: List[List[Any]]) -> List[str]:
    if not rows:
        return ["missing_columns_failed_empty"]
    idx = random.randrange(len(rows))
    row = rows[idx]
    # Remove last reading
    row.pop()
    return ["missing_columns_in_row"]


def inject_invalid_reading(rows: List[List[Any]]) -> List[str]:
    if not rows:
        return ["invalid_reading_failed_empty"]
    idx = random.randrange(len(rows))
    col = random.randrange(2, len(rows[idx]))
    rows[idx][col] = 10.0  # invalid >= 9.9
    return ["reading_value_out_of_range"]


def inject_malformed_line(file_path: Path) -> List[str]:
    # Append a malformed CSV line (unbalanced quote)
    with file_path.open("a", encoding="utf-8") as f:
        f.write('"123,"14:01:04",1,2,3,4,5,6,7,8,9,10\n')
    return ["malformed_line_unbalanced_quote"]


def choose_invalid_header() -> List[str]:
    return random.choice(HEADER_VARIANTS)


INJECTION_FUNCS = [
    (inject_duplicate_batch, "duplicate_batch_id"),
    (inject_missing_columns, "missing_columns_in_row"),
    (inject_invalid_reading, "reading_value_out_of_range"),
]


def build_rows(num: int, start_batch: int) -> List[List[Any]]:
    rows: List[List[Any]] = []
    timestamp = RANDOM_TS_BASE
    for i in range(num):
        batch_id = start_batch + i
        # Potentially vary timestamp by small seconds
        ts = timestamp + timedelta(seconds=random.randint(0,5))
        rows.append(generate_valid_row(batch_id, ts))
    return rows


def write_csv(path: Path, headers: List[str], rows: Iterable[List[Any]]):
    with path.open("w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(r)


def create_empty_file(path: Path):
    path.touch()


def generate_files(out_dir: Path, total: int, valid_ratio: float, seed: Optional[int]=None, resume: bool=True) -> Dict[str, Any]:
    """Core generation routine.

    Args:
        out_dir: Target directory for CSV artifacts.
        total:   Number of files to create.
        valid_ratio: Approximate fraction of files that should be valid.
        seed:    Optional RNG seed for reproducibility.
        resume:  If True, scan existing files to continue timestamps & batch_ids.

    Returns dict summary with counts and (internal) descriptor list removed
    before final log emission.
    """
    if seed is not None:
        random.seed(seed)

    # out_dir.mkdir(parents=True, exist_ok=True)
    descriptors: List[FileDescriptor] = []

    target_valid = int(total * valid_ratio)
    target_invalid = total - target_valid

    existing_latest_ts, existing_batch_ids = scan_existing(out_dir) if resume else (None, set())

    # Determine starting timestamp base offset
    base_time = RANDOM_TS_BASE
    if existing_latest_ts:
        # Start one second after latest existing timestamp
        if existing_latest_ts >= base_time:
            base_time = existing_latest_ts + timedelta(seconds=1)

    # Choose starting batch id past any existing ids
    batch_counter = (max(existing_batch_ids) + 10) if existing_batch_ids else 1

    for i in range(total):
        base_dt = base_time + timedelta(seconds=i)
        fname = random_filename(base_dt)
        is_valid = True
        issues: List[str] = []

        rows = build_rows(random.randint(8,12), batch_counter)  # row count variability
        batch_counter += len(rows) + 5  # ensure uniqueness spacing

        filename_to_use = fname
        headers = VALID_HEADERS.copy()

        # Decide if this file should be invalid while enforcing target proportions
        produced_valid = sum(1 for d in descriptors if d.is_valid)
        produced_invalid = len(descriptors) - produced_valid
        remaining_files = total - i
        remaining_valid_needed = max(0, target_valid - produced_valid)
        remaining_invalid_needed = max(0, target_invalid - produced_invalid)

        if remaining_invalid_needed == 0:
            make_invalid = False
        elif remaining_valid_needed == 0:
            make_invalid = True
        else:
            # Weighted bias toward producing valid files so ratio drifts toward > target_valid if randomness fluctuates
            bias = 0.65  # probability to choose valid when both slots remain
            make_invalid = random.random() > bias

        if make_invalid:
            # Randomly choose an invalidity category
            category = random.choice([
                "bad_filename","duplicate_batch","bad_header","missing_columns","invalid_reading","empty_file","malformed_line"
            ])
            if category == "bad_filename":
                filename_to_use = corrupt_filename(fname)
                is_valid = False
                issues.append("incorrect_filename_format")
            elif category == "duplicate_batch":
                issues.extend(inject_duplicate_batch(rows))
                is_valid = False
            elif category == "bad_header":
                headers = choose_invalid_header()
                is_valid = False
                issues.append("invalid_or_missing_headers")
            elif category == "missing_columns":
                issues.extend(inject_missing_columns(rows))
                is_valid = False
            elif category == "invalid_reading":
                issues.extend(inject_invalid_reading(rows))
                is_valid = False
            elif category == "empty_file":
                filename_to_use = fname  # keep valid name
                path = out_dir / filename_to_use
                create_empty_file(path)
                descriptors.append(FileDescriptor(filename_to_use, False, ["empty_file"], 0, []))
                continue
            elif category == "malformed_line":
                # Write valid content first then append malformed
                path = out_dir / filename_to_use
                write_csv(path, headers, rows)
                issues.extend(inject_malformed_line(path))
                is_valid = False
                descriptors.append(FileDescriptor(filename_to_use, False, issues, len(rows), [r[0] for r in rows]))
                continue

        path = out_dir / filename_to_use
        write_csv(path, headers, rows)

        descriptors.append(FileDescriptor(filename_to_use, is_valid, issues, len(rows), [r[0] for r in rows]))

    # Write logs
    log_json_path = out_dir / "generation_log.json"
    log_err_path = out_dir / "generation_errors.log"

    with log_json_path.open("w", encoding="utf-8") as jf:
        json.dump([asdict(d) for d in descriptors], jf, indent=2)

    with log_err_path.open("w", encoding="utf-8") as ef:
        for d in descriptors:
            if not d.is_valid:
                ef.write(f"{d.filename}: {', '.join(d.issues)}\n")

    return {
        "total": total,
        "valid": sum(1 for d in descriptors if d.is_valid),
        "invalid": sum(1 for d in descriptors if not d.is_valid),
        "output_dir": str(out_dir),
        "descriptors": descriptors,  # include for optional verification summary
    }


def parse_args():
    p = argparse.ArgumentParser(description="Generate MED_DATA CSV test files")
    # Default output now targets FTP server root so files are immediately listable by the FTP server
    default_out = Path(__file__).resolve().parent / 'ftp-roots' / 'default'
    p.add_argument("--out", type=Path, default=default_out, help="Output directory for CSV files (default: ftp-roots/default)")
    p.add_argument("--total", type=int, default=50, help="Total files to generate")
    # Increase default valid ratio so majority of generated files are valid
    p.add_argument("--valid-ratio", type=float, default=0.7, help="Ratio of valid files (0-1)")
    p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    p.add_argument("--verify", action="store_true", help="After generation, run validator on each file and report summary alignment.")
    p.add_argument("--no-resume", action="store_true", help="Do not scan existing files; start fresh at base timestamp and batch ids.")
    return p.parse_args()


def _attempt_import_validator():
    """Attempt to import the shared validate_file function used by the backend.
    Returns None if not available."""
    validator_dir = Path(__file__).resolve().parent.parent / 'interface' / 'ftp_client_backend'
    if validator_dir.exists():
        if str(validator_dir) not in sys.path:
            sys.path.insert(0, str(validator_dir))
        try:
            from validate_csv import validate_file  # type: ignore
            return validate_file
        except Exception:
            return None
    return None


def main():
    """CLI entrypoint: parse args, generate files, write centralized logs,
    optionally run post-generation verification using shared validator.
    """
    args = parse_args()
    stats = generate_files(args.out, args.total, args.valid_ratio, args.seed, resume=not args.no_resume)
    descriptors = stats.pop("descriptors", [])

    # Write logs to central generation_logs directory (sibling to FTP_server)
    root = Path(__file__).resolve().parent.parent
    gen_logs = root / 'generation_logs'
    gen_logs.mkdir(parents=True, exist_ok=True)
    log_json_path = gen_logs / 'generation_log.json'
    log_err_path = gen_logs / 'generation_errors.log'
    # Reconstruct minimal records without descriptors list for json (descriptor list already removed)
    with log_json_path.open('w', encoding='utf-8') as jf:
        json.dump({k: v for k, v in stats.items()}, jf, indent=2)
    # Human-readable errors file
    with log_err_path.open('w', encoding='utf-8') as ef:
        for d in descriptors:
            if not d.is_valid:
                ef.write(f"{d.filename}: {', '.join(d.issues)}\n")

    print(json.dumps({**stats, "log_dir": str(gen_logs)}, indent=2))

    if args.verify:
        validate_file = _attempt_import_validator()
        if not validate_file:
            print("[verify] Unable to import validator (validate_csv.py). Skipping verification.")
            return
        print("[verify] Running validator over generated files...")
        valid_count = 0
        invalid_count = 0
        mismatches: List[str] = []
        for d in descriptors:  
            fp = args.out / d.filename  
            if not fp.exists():
                mismatches.append(f"MISSING_FILE:{d.filename}")
                continue
            res = validate_file(fp)
            generator_claim = d.is_valid
            validator_claim = res.is_valid
            if validator_claim:
                valid_count += 1
            else:
                invalid_count += 1
            if generator_claim != validator_claim:
                mismatches.append(f"MISMATCH:{d.filename}: gen={generator_claim} validator={validator_claim} issues={res.issues}")
        print(f"[verify] Validator counts -> valid: {valid_count} invalid: {invalid_count}")
        if mismatches:
            print("[verify] Detected mismatches (this indicates rule divergence):")
            for m in mismatches:
                print("  - " + m)
        else:
            print("[verify] Generator and validator agree on all files.")

if __name__ == "__main__":
    main()
