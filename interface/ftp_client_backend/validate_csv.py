"""Validation utility for MED_DATA CSV files.

Rules implemented (derived from assignment brief):
1. Filename must match MED_DATA_YYYYMMDDHHMMSS.csv pattern.
2. Required headers exactly: batch_id,timestamp,reading1..reading10
3. No duplicate batch_id within file.
4. Each row must have 12 columns (batch_id + timestamp + 10 readings).
5. Each reading must be a float 0 <= x < 9.9.
6. File must not be empty (0 bytes) and at least header + 1 data row.
7. CSV must be parseable (RFC4180 simplified using csv module).

Outputs JSON describing validity and issues; usable as a module or CLI.
"""
from __future__ import annotations
import re
import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple

FILENAME_RE = re.compile(r"^MED_DATA_\d{14}\.csv$")
EXPECTED_HEADERS = ["batch_id", "timestamp", *[f"reading{i}" for i in range(1,11)]]


@dataclass
class ValidationResult:
    filename: str
    is_valid: bool
    issues: List[str]
    rows: int
    duplicate_batch_ids: List[int]


class CSVValidationError(Exception):
    pass


def validate_file(path: Path) -> ValidationResult:
    """Validate a MED_DATA CSV file and return structured results.

    The validator is intentionally strict: any divergence from expected
    headers, row width, numeric constraints, or filename pattern yields
    a specific issue token for downstream filtering/logging.
    """
    issues: List[str] = []
    duplicate_batch_ids: List[int] = []

    # 1. Filename pattern
    if not FILENAME_RE.match(path.name):
        issues.append("incorrect_filename_format")

    if not path.exists():
        issues.append("file_missing")
        return ValidationResult(path.name, False, issues, 0, duplicate_batch_ids)

    if path.stat().st_size == 0:
        issues.append("empty_file")
        return ValidationResult(path.name, False, issues, 0, duplicate_batch_ids)

    try:
        with path.open('r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                issues.append("missing_headers")
                return ValidationResult(path.name, False, issues, 0, duplicate_batch_ids)

            if headers != EXPECTED_HEADERS:
                issues.append("invalid_or_missing_headers")

            seen = set()
            row_count = 0
            for row in reader:
                if not row:
                    continue  # skip blank line
                row_count += 1
                # 4. Column count
                if len(row) != len(EXPECTED_HEADERS):
                    issues.append("missing_columns_in_row")
                    # continue to gather more issues
                # Parse batch id
                try:
                    batch_id = int(row[0])
                except Exception:
                    issues.append("invalid_batch_id")
                    batch_id = None
                if batch_id is not None:
                    if batch_id in seen and batch_id not in duplicate_batch_ids:
                        duplicate_batch_ids.append(batch_id)
                    seen.add(batch_id)
                # Validate readings
                for i in range(2, min(len(row), len(EXPECTED_HEADERS))):
                    try:
                        val = float(row[i])
                        if not (0 <= val < 9.9):
                            issues.append("reading_value_out_of_range")
                            break  # one per row sufficient
                    except ValueError:
                        issues.append("non_numeric_reading")
                        break

            if duplicate_batch_ids:
                issues.append("duplicate_batch_id")

            if row_count == 0:
                issues.append("no_data_rows")
            is_valid = len(issues) == 0
            return ValidationResult(path.name, is_valid, sorted(set(issues)), row_count, duplicate_batch_ids)
    except csv.Error:
        issues.append("malformed_csv")
    except Exception:
        issues.append("unreadable_file")
    return ValidationResult(path.name, False, sorted(set(issues)), 0, duplicate_batch_ids)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Validate MED_DATA CSV file(s)")
    ap.add_argument('files', nargs='+', help='CSV files to validate')
    ap.add_argument('--json', action='store_true', help='Emit JSON array')
    args = ap.parse_args()
    results = [validate_file(Path(p)) for p in args.files]
    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for r in results:
            status = 'VALID' if r.is_valid else 'INVALID'
            print(f"{r.filename}: {status}")
            if r.issues:
                print("  Issues: " + ", ".join(r.issues))
            if r.duplicate_batch_ids:
                print("  Duplicates: " + ", ".join(map(str, r.duplicate_batch_ids)))


if __name__ == '__main__':
    main()
