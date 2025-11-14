from pathlib import Path
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interface.ftp_client_backend.validate_csv import validate_file, EXPECTED_HEADERS


def make_good_csv(tmp_path: Path, name: str = "MED_DATA_20240603140104.csv") -> Path:
    p = tmp_path / name
    lines = [','.join(EXPECTED_HEADERS)]
    # add 3 valid rows
    for i in range(3):
        row = [str(100+i), "14:01:04"] + ["1.23" for _ in range(10)]
        lines.append(','.join(row))
    p.write_text('\n'.join(lines), encoding='utf-8')
    return p


def test_validator_accepts_valid(tmp_path: Path):
    good = make_good_csv(tmp_path)
    res = validate_file(good)
    assert res.is_valid, res.issues


def test_validator_detects_bad_header(tmp_path: Path):
    bad = make_good_csv(tmp_path, "MED_DATA_20240603140105.csv")
    content = bad.read_text(encoding='utf-8').replace('batch_id', 'batch')
    bad.write_text(content, encoding='utf-8')
    res = validate_file(bad)
    assert not res.is_valid
    assert 'invalid_or_missing_headers' in res.issues
