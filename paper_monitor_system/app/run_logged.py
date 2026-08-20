from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime

from .config import BUILD_ID, REPO_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream V6 local_update output to console and log")
    parser.add_argument("--provider", default="all", choices=["all", "sciencedirect", "springer", "ieee"])
    parser.add_argument("--initial-days", type=int, default=7)
    parser.add_argument("--no-git", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    log_dir = REPO_ROOT / "paper_monitor_system" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    cmd = [
        sys.executable, "-u", "-m", "paper_monitor_system.app.local_update",
        "--provider", args.provider, "--initial-days", str(args.initial_days),
    ]
    if args.no_git: cmd.append("--no-git")
    if args.no_push: cmd.append("--no-push")
    if args.skip_tests: cmd.append("--skip-tests")

    print(f"Paper monitor {BUILD_ID} update")
    print(f"Log: {log_file}\n")
    with log_file.open("w", encoding="utf-8", errors="replace") as log:
        log.write("Command: " + " ".join(cmd) + "\n\n")
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log.write(line)
            log.flush()
        code = proc.wait()
    print()
    if code == 0:
        print("Paper monitor update completed successfully.")
    else:
        print(f"Paper monitor update FAILED with exit code {code}.")
        print(f"Review: {log_file}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
