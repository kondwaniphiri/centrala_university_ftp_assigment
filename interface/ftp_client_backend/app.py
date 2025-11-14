import io
import os
import uuid
import json
import re
import datetime as dt
from ftplib import FTP, error_perm
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess
import urllib.request
from pathlib import Path

from validate_csv import validate_file  # local validation logic

app = Flask(__name__)
CORS(app)

# --- Paths / Storage Setup -------------------------------------------------
BASE_DOWNLOAD_DIR = Path(__file__).resolve().parent / 'downloads'
BASE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = Path(__file__).resolve().parent / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_LOG = LOG_DIR / 'download_log.json'
ERROR_LOG = LOG_DIR / 'validation_errors.log'
TRACKING_FILE = LOG_DIR / 'downloaded_files.txt'  # list of successfully validated filenames
WEB_CLIENT_DOWNLOAD_BASE = Path(__file__).resolve().parent.parent / 'web_client' / 'downloads'
WEB_CLIENT_DOWNLOAD_BASE.mkdir(parents=True, exist_ok=True)

FILENAME_RE = re.compile(r"^MED_DATA_\d{14}\.csv$")

def load_download_log():
    if DOWNLOAD_LOG.exists():
        try:
            return json.loads(DOWNLOAD_LOG.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []

def append_download_entry(entry: dict):
    log = load_download_log()
    log.append(entry)
    DOWNLOAD_LOG.write_text(json.dumps(log, indent=2), encoding='utf-8')

def append_tracking(filename: str):
    existing = set()
    if TRACKING_FILE.exists():
        existing = set(TRACKING_FILE.read_text(encoding='utf-8').splitlines())
    if filename not in existing:
        with TRACKING_FILE.open('a', encoding='utf-8') as f:
            f.write(filename + '\n')

def has_downloaded(filename: str) -> bool:
    if not TRACKING_FILE.exists():
        return False
    return filename in TRACKING_FILE.read_text(encoding='utf-8').splitlines()

def fetch_guid() -> str:
    """Fetch a V1 UUID from external API; fall back to local uuid if fails."""
    try:
        with urllib.request.urlopen('https://www.uuidtools.com/api/generate/v1', timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if isinstance(data, list) and data:
                return data[0]
    except Exception:
        pass
    return str(uuid.uuid1())

def log_validation_error(filename: str, issues):
    guid = fetch_guid()
    timestamp = dt.datetime.utcnow().isoformat() + 'Z'
    line = f"{timestamp} {guid} {filename} {','.join(sorted(set(issues)))}"
    with ERROR_LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')
    return guid

def load_invalid_filenames() -> set[str]:
    """Parse validation_errors.log and return set of filenames previously marked invalid."""
    invalid = set()
    if not ERROR_LOG.exists():
        return invalid
    try:
        for line in ERROR_LOG.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            # Format: timestamp guid filename issues_csv
            parts = line.split(' ', 3)
            if len(parts) >= 3:
                invalid.add(parts[2])
    except Exception:
        pass
    return invalid

def monthly_dir(now: dt.datetime | None = None) -> Path:
    now = now or dt.datetime.utcnow()
    d = BASE_DOWNLOAD_DIR / f"{now.year:04d}-{now.month:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d

# --- Session Management -----------------------------------------------------
# In-memory token -> ftplib.FTP connection map. Intended only for demo use.
SESSIONS = {}


def get_conn(token: str):
    conn = SESSIONS.get(token)
    if conn is None:
        return None, ("invalid_session", 401)
    return conn, None


@app.post('/api/connect')
def connect():
    data = request.get_json(force=True)
    host = data.get('host')
    port = int(data.get('port', 21))
    user = data.get('user', '')
    password = data.get('password', '')
    timeout = int(data.get('timeout', 10))
    diagnostics = {}
    try:
        ftp = FTP()
        ftp.connect(host, port, timeout=timeout)
        diagnostics['connect'] = 'ok'
        diagnostics['welcome'] = ftp.getwelcome() if hasattr(ftp, 'getwelcome') else ''
        resp = ftp.login(user, password)
        diagnostics['login'] = resp
        # Some servers may 5xx on PWD or other immediate commands; treat as soft failure
        try:
            pwd = ftp.pwd()
        except Exception as e_pwd:
            diagnostics['pwd_error'] = str(e_pwd)
            # Attempt a benign NOOP to verify control channel
            try:
                ftp.voidcmd('NOOP')
                diagnostics['noop'] = 'ok'
            except Exception as e_noop:
                diagnostics['noop_error'] = str(e_noop)
            pwd = ''
        token = str(uuid.uuid4())
        SESSIONS[token] = ftp
        return jsonify({"token": token, "pwd": pwd, "diagnostics": diagnostics}), 200
    except Exception as e:
        diagnostics['exception'] = str(e)
        return jsonify({"error": "connection_failed", "details": diagnostics}), 400


@app.get('/api/health')
def health():
    return jsonify({"status": "ok", "active_sessions": len(SESSIONS)})


@app.post('/api/ftp-probe')
def ftp_probe():
    """Probe a single FTP connect/login to validate credentials without creating a session."""
    data = request.get_json(force=True)
    host = data.get('host')
    port = int(data.get('port', 21))
    user = data.get('user', '')
    password = data.get('password', '')
    timeout = int(data.get('timeout', 5))
    diagnostics = {}
    try:
        ftp = FTP()
        ftp.connect(host, port, timeout=timeout)
        diagnostics['connect'] = 'ok'
        diagnostics['welcome'] = ftp.getwelcome() if hasattr(ftp, 'getwelcome') else ''
        diagnostics['login_reply'] = ftp.login(user, password)
        try:
            diagnostics['pwd'] = ftp.pwd()
        except Exception as e_pwd:
            diagnostics['pwd_error'] = str(e_pwd)
        ftp.quit()
        return jsonify({'ok': True, 'diagnostics': diagnostics})
    except Exception as e:
        diagnostics['exception'] = str(e)
        return jsonify({'ok': False, 'diagnostics': diagnostics}), 400


@app.post('/api/debug-connect')
def debug_connect():
    """Perform a connect with ftplib debug output captured and returned."""
    data = request.get_json(force=True)
    host = data.get('host')
    port = int(data.get('port', 21))
    user = data.get('user', '')
    password = data.get('password', '')
    timeout = int(data.get('timeout', 10))
    import io as _io, contextlib
    log_buf = _io.StringIO()
    class DebugFTP(FTP):
        pass
    ftp = DebugFTP()
    ftp.set_debuglevel(2)  # verbose
    # monkeypatch ftp.write to capture? ftplib prints to stdout; capture using redirect_stdout
    try:
        with contextlib.redirect_stdout(log_buf):
            ftp.connect(host, port, timeout=timeout)
            ftp.login(user, password)
            try:
                pwd = ftp.pwd()
            except Exception as e_pwd:
                pwd = ''
                log_buf.write(f"\nPWD error: {e_pwd}\n")
            ftp.quit()
        return jsonify({
            'ok': True,
            'trace': log_buf.getvalue(),
            'pwd': pwd
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'trace': log_buf.getvalue(),
            'error': str(e)
        }), 400


@app.post('/api/disconnect')
def disconnect():
    data = request.get_json(force=True)
    token = data.get('token')
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    try:
        conn.quit()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
    finally:
        SESSIONS.pop(token, None)
    return jsonify({"ok": True})


@app.post('/api/list')
def list_dir():
    data = request.get_json(force=True)
    token = data.get('token')
    path = data.get('path', None)
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    try:
        if path:
            conn.cwd(path)
        items = []
        conn.retrlines('LIST', items.append)
        return jsonify({"lines": items, "pwd": conn.pwd()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post('/api/cwd')
def change_dir():
    data = request.get_json(force=True)
    token = data.get('token')
    path = data.get('path')
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    try:
        conn.cwd(path)
        return jsonify({"pwd": conn.pwd()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post('/api/mkdir')
def mkdir():
    data = request.get_json(force=True)
    token = data.get('token')
    name = data.get('name')
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    try:
        conn.mkd(name)
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post('/api/delete')
def delete():
    data = request.get_json(force=True)
    token = data.get('token')
    name = data.get('name')
    is_dir = bool(data.get('isDir', False))
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    try:
        if is_dir:
            conn.rmd(name)
        else:
            conn.delete(name)
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post('/api/rename')
def rename():
    data = request.get_json(force=True)
    token = data.get('token')
    old = data.get('old')
    new = data.get('new')
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    try:
        conn.rename(old, new)
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post('/api/upload')
def upload():
    token = request.form.get('token')
    path = request.form.get('path', '.')
    file = request.files.get('file')
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    if not file:
        return jsonify({"error": "no_file"}), 400
    try:
        if path:
            conn.cwd(path)
        conn.storbinary(f'STOR {file.filename}', file.stream)
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get('/api/download')
def download():
    token = request.args.get('token')
    name = request.args.get('name')
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    if not name:
        return jsonify({"error": "missing_name"}), 400
    try:
        buff = io.BytesIO()
        conn.retrbinary(f'RETR {name}', buff.write)
        buff.seek(0)
        return send_file(buff, as_attachment=True, download_name=name)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post('/api/list-files')
def list_files_parsed():
    """Return a parsed list of candidate files (CSV) in current directory, with downloaded flag."""
    data = request.get_json(force=True)
    token = data.get('token')
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    try:
        names = []
        conn.retrlines('NLST', names.append)
        previously_invalid = load_invalid_filenames()
        files = []
        for n in names:
            if not n.lower().endswith('.csv'):
                continue
            # Exclude if previously invalid
            if n in previously_invalid:
                continue
            # Exclude if already downloaded (accepted valid file)
            if has_downloaded(n):
                continue
            files.append({
                'name': n,
                'matches_pattern': bool(FILENAME_RE.match(n)),
                'downloaded': False
            })
        return jsonify({'files': files}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def _download_raw(conn: FTP, name: str) -> bytes:
    buff = io.BytesIO()
    conn.retrbinary(f'RETR {name}', buff.write)
    return buff.getvalue()


@app.post('/api/bulk-download')
def bulk_download():
    """Download multiple CSV files, validate, store monthly; return per-file status.
    Request JSON: { token: str, files: ["MED_DATA_...csv"], skipDownloaded: bool }
    """
    data = request.get_json(force=True)
    token = data.get('token')
    files = data.get('files', [])
    skip_downloaded = bool(data.get('skipDownloaded', True))
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    results = []
    previously_invalid = load_invalid_filenames()
    for name in files:
        if name in previously_invalid:
            results.append({'name': name, 'skipped': True, 'reason': 'previously_invalid'})
            continue
        if skip_downloaded and has_downloaded(name):
            results.append({
                'name': name,
                'skipped': True,
                'reason': 'already_downloaded'
            })
            continue
        try:
            raw = _download_raw(conn, name)
            # IMPORTANT: Write using the ORIGINAL filename so validator's filename pattern check passes.
            # Previously we used a prefixed temp name which caused every file to fail pattern validation.
            target_dir = monthly_dir()
            temp_path = target_dir / name
            # If a stale partial file exists (crash in prior run), remove it before writing.
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            with temp_path.open('wb') as f:
                f.write(raw)
            vres = validate_file(temp_path)
            entry = {
                'name': name,
                'valid': vres.is_valid,
                'issues': vres.issues,
                'rows': vres.rows,
            }
            if vres.is_valid:
                final_path = temp_path  # already correct location/name
                append_tracking(name)
                # Copy to web client downloads mirror
                try:
                    web_month = WEB_CLIENT_DOWNLOAD_BASE / final_path.parent.name
                    web_month.mkdir(parents=True, exist_ok=True)
                    mirror_path = web_month / name
                    # Copy file bytes
                    with final_path.open('rb') as src, mirror_path.open('wb') as dst:
                        dst.write(src.read())
                    entry['web_client_path'] = str(mirror_path.relative_to(WEB_CLIENT_DOWNLOAD_BASE))
                except Exception as e_copy:
                    entry['web_copy_error'] = str(e_copy)
                entry['stored_path'] = str(final_path.relative_to(BASE_DOWNLOAD_DIR))
                append_download_entry({
                    'timestamp': dt.datetime.utcnow().isoformat() + 'Z',
                    'filename': name,
                    'stored_path': entry['stored_path'],
                    'rows': vres.rows
                })
            else:
                guid = log_validation_error(name, vres.issues)
                entry['error_guid'] = guid
                # Remove invalid file so it doesn't appear as downloaded artifact
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            results.append(entry)
        except error_perm as e:
            results.append({'name': name, 'error': str(e)})
        except Exception as e:
            results.append({'name': name, 'error': str(e)})
    return jsonify({'results': results}), 200


@app.post('/api/new-files')
def new_files():
    """Return names of CSV files on server not yet downloaded (validated)."""
    data = request.get_json(force=True)
    token = data.get('token')
    conn, err = get_conn(token)
    if err:
        return jsonify({"error": err[0]}), err[1]
    names = []
    try:
        conn.retrlines('NLST', names.append)
        previously_invalid = load_invalid_filenames()
        missing = [
            n for n in names
            if n.lower().endswith('.csv')
            and n not in previously_invalid
            and not has_downloaded(n)
        ]
        return jsonify({'new': missing}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post('/api/reset-state')
def reset_state():
    """Reset logs and (optionally) downloaded storage.
    JSON body: { purgeDownloads: bool }
    """
    data = request.get_json(force=True, silent=True) or {}
    purge = bool(data.get('purgeDownloads', False))
    removed = []
    errors = []
    targets = [ERROR_LOG, DOWNLOAD_LOG, TRACKING_FILE]
    for p in targets:
        try:
            if p.exists():
                p.unlink()
                removed.append(p.name)
        except Exception as e:
            errors.append({ 'file': p.name, 'error': str(e) })
    purged_dirs = []
    if purge:
        # Remove contents of monthly download dirs and web mirrors
        def _clear_dir(d: Path):
            if not d.exists():
                return
            for child in list(d.iterdir()):
                try:
                    if child.is_dir():
                        for sub in list(child.iterdir()):
                            if sub.is_file():
                                sub.unlink()
                            else:
                                import shutil
                                shutil.rmtree(sub)
                        child.rmdir()
                    else:
                        child.unlink()
                except Exception as ce:
                    errors.append({'file': str(child), 'error': str(ce)})
        try:
            _clear_dir(BASE_DOWNLOAD_DIR)
            purged_dirs.append(str(BASE_DOWNLOAD_DIR))
        except Exception as e:
            errors.append({'dir': str(BASE_DOWNLOAD_DIR), 'error': str(e)})
        try:
            _clear_dir(WEB_CLIENT_DOWNLOAD_BASE)
            purged_dirs.append(str(WEB_CLIENT_DOWNLOAD_BASE))
        except Exception as e:
            errors.append({'dir': str(WEB_CLIENT_DOWNLOAD_BASE), 'error': str(e)})
    return jsonify({
        'removed_files': removed,
        'purged_download_dirs': purged_dirs,
        'errors': errors
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
