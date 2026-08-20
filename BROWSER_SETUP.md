# Browser setup for ScienceDirect and IEEE Xplore

V6 uses Playwright with a persistent browser profile because the publisher sites rejected earlier `requests`/cloud-runner traffic.

## Recommended Windows settings

```text
BROWSER_CHANNEL=chromium
BROWSER_HEADLESS=false
```

Run `browser_warmup.bat` once. Two tabs open in the dedicated profile:

- ScienceDirect search for the first monitored Elsevier journal
- IEEE Xplore search for the first monitored IEEE journal

Accept normal cookie/consent dialogs if necessary. Do not use your everyday Chrome profile; V6 keeps its own profile under `paper_monitor_system/browser_profile/`.

## If Chrome cannot launch

`setup_local.bat` also attempts `python -m playwright install chromium`. If that download succeeds, V6 automatically falls back to bundled Chromium when `chromium` is unavailable.

## Task Scheduler

With headed mode, choose **Run only when user is logged on**. This lets Chrome/Chromium render normally at the scheduled time. If you later verify that `BROWSER_HEADLESS=true` returns the same results, headless mode can run without visible windows.


V6.1 Chrome build: browser executable can be set by BROWSER_EXECUTABLE_PATH. Default configured for C:\Program Files (x86)\Chrome\App\chrome.exe.
