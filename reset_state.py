"""Reset application state for the MED_DATA demo.

Removes:
  - interface/ftp_client_backend/logs/*.log (validation + download logs)
  - interface/ftp_client_backend/logs/downloaded_files.txt
  - interface/ftp_client_backend/downloads/* (stored validated files)
  - interface/web_client/downloads/* (mirrored files)

Usage (PowerShell):
    python reset_state.py --all
    python reset_state.py --logs-only

By default (no flags) it performs a full reset (same as --all).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / 'interface' / 'ftp_client_backend'
LOG_DIR = BACKEND / 'logs'
BACKEND_DL = BACKEND / 'downloads'
WEB_DL = ROOT / 'interface' / 'web_client' / 'downloads'

LOG_FILES = [
    LOG_DIR / 'validation_errors.log',
    LOG_DIR / 'download_log.json',
    LOG_DIR / 'downloaded_files.txt'
]

def remove_file(p: Path):
    """Delete a single file if it exists (best-effort)."""
    try:
        if p.exists():
            p.unlink()
            print(f"Removed file: {p}")
    except Exception as e:
        print(f"Failed to remove {p}: {e}")


def clear_dir_contents(d: Path):
    """Remove all children (files & subdirectories) from a directory without deleting the directory itself."""
    if not d.exists():
        return
    for child in d.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
                print(f"Removed directory: {child}")
            else:
                child.unlink()
                print(f"Removed file: {child}")
        except Exception as e:
            print(f"Failed to remove {child}: {e}")


def reset(all_: bool, logs_only: bool):
    """Perform the reset according to provided flags.

    Precedence: --all overrides --logs-only; default action is full reset.
    """
    if logs_only and all_:
        logs_only = False  # all overrides logs_only
    if not (logs_only or all_):
        all_ = True  # default behavior

    # Always handle logs
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for lf in LOG_FILES:
        remove_file(lf)

    if all_ and not logs_only:
        BACKEND_DL.mkdir(parents=True, exist_ok=True)
        WEB_DL.mkdir(parents=True, exist_ok=True)
        clear_dir_contents(BACKEND_DL)
        clear_dir_contents(WEB_DL)

    # Summary
    print("State reset complete.")


def parse_args():
    ap = argparse.ArgumentParser(description="Reset state (logs, downloads, mirrors)")
    ap.add_argument('--all', action='store_true', help='Remove logs + backend downloads + web downloads (default)')
    ap.add_argument('--logs-only', action='store_true', help='Only remove log/tracking files')
    return ap.parse_args()


def main():
    args = parse_args()
    reset(args.all, args.logs_only)

if __name__ == '__main__':
    main()
