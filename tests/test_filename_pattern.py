import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interface.ftp_client_backend.validate_csv import FILENAME_RE as FILENAME_PATTERN


def test_filename_pattern_valid():
    assert FILENAME_PATTERN.match('MED_DATA_20240603140104.csv')
    assert FILENAME_PATTERN.match('MED_DATA_19991231235959.csv')


def test_filename_pattern_invalid():
    assert not FILENAME_PATTERN.match('MED_DATA_20240603140104.CSVX')
    assert not FILENAME_PATTERN.match('BAD_DATA_20240603140104.csv')
    # Note: Pattern does not enforce calendar validity; only structural digits
