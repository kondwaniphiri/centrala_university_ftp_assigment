import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'interface' / 'ftp_client_backend'))
import app as backend
from validate_csv import EXPECTED_HEADERS


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, 'BASE_DOWNLOAD_DIR', tmp_path / 'downloads')
    monkeypatch.setattr(backend, 'WEB_CLIENT_DOWNLOAD_BASE', tmp_path / 'mirror')
    monkeypatch.setattr(backend, 'DOWNLOAD_LOG', tmp_path / 'log.json')
    monkeypatch.setattr(backend, 'TRACKING_FILE', tmp_path / 'tracking.txt')
    monkeypatch.setattr(backend, 'ERROR_LOG', tmp_path / 'errors.log')
    monkeypatch.setattr(backend, 'fetch_guid', lambda: 'test-guid')
    monkeypatch.setattr(backend, 'SESSIONS', {'test': object()})
    return backend.app.test_client()


@pytest.mark.parametrize('name', ['../victim.csv', 'C:\\victim.csv', '/victim.csv', 'bad\r\nDELE victim.csv'])
def test_bulk_rejects_paths_before_ftp(client, monkeypatch, name):
    def unexpected_download(*args):
        pytest.fail('Unsafe filename reached FTP')
    monkeypatch.setattr(backend, '_download_raw', unexpected_download)
    response = client.post('/api/bulk-download', json={'token': 'test', 'files': [name]})
    assert response.json['results'][0]['error'] == 'invalid_filename'


def test_bulk_accepts_valid_and_cleans_staging(client, monkeypatch):
    raw = (','.join(EXPECTED_HEADERS) + '\n1,14:01:04,' + ','.join(['1.2'] * 10)).encode()
    monkeypatch.setattr(backend, '_download_raw', lambda *args: raw)
    name = 'MED_DATA_20240603140104.csv'
    response = client.post('/api/bulk-download', json={'token': 'test', 'files': [name]})
    assert response.json['results'][0]['valid']
    assert backend.has_downloaded(name)
    assert list(backend.BASE_DOWNLOAD_DIR.rglob('*.csv'))[0].read_bytes() == raw
    assert not any(p.is_dir() for p in next(backend.BASE_DOWNLOAD_DIR.iterdir()).iterdir())


def test_bulk_removes_invalid_staging(client, monkeypatch):
    monkeypatch.setattr(backend, '_download_raw', lambda *args: b'bad csv')
    response = client.post('/api/bulk-download', json={
        'token': 'test', 'files': ['MED_DATA_20240603140104.csv']})
    assert response.json['results'][0]['valid'] is False
    assert not list(backend.BASE_DOWNLOAD_DIR.rglob('*.csv'))


def test_reset_requires_session(client):
    assert client.post('/api/reset-state', json={}).status_code == 401


def test_bad_filename_is_logged_without_download(client, monkeypatch):
    def unexpected_download(*args):
        pytest.fail('Invalid filename reached FTP')
    monkeypatch.setattr(backend, '_download_raw', unexpected_download)
    name = 'med_data_20240603140104.csv'
    response = client.post('/api/bulk-download', json={'token': 'test', 'files': [name]})
    assert response.json['results'][0]['valid'] is False
    assert name in backend.load_invalid_filenames()


def test_bulk_requires_file_list(client):
    assert client.post('/api/bulk-download', json={
        'token': 'test', 'files': 'file.csv'}).status_code == 400


@pytest.mark.parametrize('settings', [
    {'host': 'localhost', 'port': 'invalid'},
    {'host': 'localhost', 'port': 70000},
    {'host': '', 'port': 2121},
    {'host': 'localhost', 'timeout': 0},
])
def test_connect_rejects_invalid_settings(client, settings):
    response = client.post('/api/connect', json=settings)
    assert response.status_code == 400
    assert response.json['error'] == 'invalid_connection_settings'
