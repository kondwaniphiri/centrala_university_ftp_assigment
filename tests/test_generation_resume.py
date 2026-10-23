import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from FTP_server.generate_csv_data import generate_files, inject_duplicate_batch, corrupt_filename
from interface.ftp_client_backend.validate_csv import validate_file, FILENAME_RE


def test_resume_preserves_files_and_advances_ids(tmp_path):
    output = tmp_path / 'new-directory'
    first = generate_files(output, 5, 1, seed=42)
    originals = {d.filename: (output / d.filename).read_bytes() for d in first['descriptors']}
    second = generate_files(output, 5, 1, seed=43)
    assert not set(originals) & {d.filename for d in second['descriptors']}
    assert all((output / name).read_bytes() == raw for name, raw in originals.items())
    assert min(b for d in second['descriptors'] for b in d.batch_ids) > max(
        b for d in first['descriptors'] for b in d.batch_ids)


def test_generated_validity_agrees_with_validator(tmp_path):
    stats = generate_files(tmp_path, 200, 0.5, seed=42)
    for descriptor in stats['descriptors']:
        result = validate_file(tmp_path / descriptor.filename)
        assert result.is_valid == descriptor.is_valid, descriptor.filename


def test_injections_always_change_validity():
    for _ in range(100):
        rows = [[1, '14:01:04'], [2, '14:01:04']]
        inject_duplicate_batch(rows)
        assert rows[0][0] == rows[1][0]
        assert not FILENAME_RE.fullmatch(corrupt_filename('MED_DATA_20240603140104.csv'))


def test_no_resume_refuses_overwrite(tmp_path):
    generate_files(tmp_path, 1, 1)
    with pytest.raises(ValueError):
        generate_files(tmp_path, 1, 1, resume=False)
