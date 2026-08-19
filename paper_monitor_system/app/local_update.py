from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .config import BUILD_ID, DB_PATH, REPO_ROOT, WEB_JSON_PATH


def run(cmd: list[str], *, cwd: Path = REPO_ROOT, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd), check=check, text=True)


def git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def ensure_clean_repo() -> None:
    result = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    dirty = result.stdout.strip()
    if dirty:
        raise SystemExit(
            "Git working tree has uncommitted changes. Commit/stash them first, then rerun update_papers.bat.\n" + dirty
        )


def current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True
    )
    branch = result.stdout.strip()
    if not branch or branch == "HEAD":
        raise SystemExit("Could not determine the current Git branch.")
    return branch


def sync(provider: str, initial_days: int, skip_tests: bool) -> None:
    if not skip_tests:
        run([sys.executable, "-m", "paper_monitor_system.app.selfcheck"])
        run([sys.executable, "-m", "paper_monitor_system.app.selftest"])
    run([
        sys.executable, "-m", "paper_monitor_system.app.sync",
        "--provider", provider,
        "--initial-days", str(initial_days),
    ])


def publish(branch: str) -> None:
    if not DB_PATH.exists() or not WEB_JSON_PATH.exists():
        raise SystemExit("Generated papers.db or online_papers.json is missing; refusing to publish.")

    run(["git", "add", str(DB_PATH.relative_to(REPO_ROOT)), str(WEB_JSON_PATH.relative_to(REPO_ROOT))])
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(REPO_ROOT))
    if diff.returncode == 0:
        print("No paper-monitor data changes to commit.")
        return
    if diff.returncode not in (0, 1):
        raise SystemExit("git diff --cached failed")

    run(["git", "commit", "-m", "chore: update paper monitor"])
    result = subprocess.run(["git", "push", "origin", branch], cwd=str(REPO_ROOT))
    if result.returncode == 0:
        print("Paper-monitor data pushed successfully.")
        return

    # Safe race recovery: preserve only the two generated artifacts, reset to the
    # latest remote branch, restore the generated artifacts, recommit and push.
    print("Remote branch changed during the update; retrying safely from latest origin.")
    with tempfile.TemporaryDirectory(prefix="paper-monitor-") as td:
        td = Path(td)
        db_copy = td / "papers.db"
        json_copy = td / "online_papers.json"
        shutil.copy2(DB_PATH, db_copy)
        shutil.copy2(WEB_JSON_PATH, json_copy)
        run(["git", "fetch", "origin", branch])
        run(["git", "reset", "--hard", f"origin/{branch}"])
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_copy, DB_PATH)
        shutil.copy2(json_copy, WEB_JSON_PATH)
        run(["git", "add", str(DB_PATH.relative_to(REPO_ROOT)), str(WEB_JSON_PATH.relative_to(REPO_ROOT))])
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(REPO_ROOT))
        if diff.returncode == 0:
            print("Latest remote already contains the generated data.")
            return
        run(["git", "commit", "-m", "chore: update paper monitor"])
        run(["git", "push", "origin", branch])


def main() -> None:
    parser = argparse.ArgumentParser(description="Local paper-monitor updater for Windows/macOS/Linux")
    parser.add_argument("--provider", choices=["all", "sciencedirect", "springer", "ieee"], default="all")
    parser.add_argument("--initial-days", type=int, default=1)
    parser.add_argument("--no-git", action="store_true", help="fetch/export only; do not pull/commit/push")
    parser.add_argument("--no-push", action="store_true", help="pull first, fetch/export, but leave generated changes uncommitted")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    print(f"Paper Monitor Build: {BUILD_ID}")
    print(f"Repository: {REPO_ROOT}")

    branch = ""
    if not args.no_git:
        if not git_available():
            raise SystemExit("Git is not installed or not available in PATH. Use --no-git or install Git for Windows.")
        ensure_clean_repo()
        branch = current_branch()
        # Always synchronize before touching the SQLite DB. Never pull/rebase after data generation.
        run(["git", "pull", "--ff-only", "origin", branch])

    sync(args.provider, args.initial_days, args.skip_tests)

    if args.no_git:
        print("Fetch/export complete. Git operations were skipped (--no-git).")
    elif args.no_push:
        print("Fetch/export complete. Generated files were left uncommitted (--no-push).")
    else:
        publish(branch)


if __name__ == "__main__":
    main()
