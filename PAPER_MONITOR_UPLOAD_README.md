FINAL FIX VERSION

Upload this package into the root of dm-dut.github.io.

It will create:
- paper-monitor/        -> https://dm-dut.github.io/paper-monitor/
- paper_monitor_system/ -> backend crawler

Do not upload API keys into files.
Configure GitHub Secrets:
ELSEVIER_API_KEY
SPRINGER_API_KEY
IEEE_API_KEY

Python imports have been migrated from:
    from app.xxx
to:
    from ..xxx

This avoids ModuleNotFoundError when running:
    python -m paper_monitor_system.app.sync