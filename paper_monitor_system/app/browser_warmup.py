from __future__ import annotations

from .config import BUILD_ID
from .journals import enabled_journals
from .providers.browser import BrowserRuntime


def main() -> None:
    print(f"Paper Monitor Build: {BUILD_ID}")
    print("Opening ScienceDirect and IEEE Xplore in the dedicated persistent browser profile.")
    print("If you see cookie/consent/access prompts, complete them once. The profile will be reused later.")
    with BrowserRuntime() as br:
        sd = br.new_page()
        ieee = br.new_page()
        sd.goto(enabled_journals("sciencedirect")[0].search_url, wait_until="domcontentloaded")
        ieee.goto(enabled_journals("ieee")[0].search_url, wait_until="domcontentloaded")
        input("\nPress Enter here after both pages are usable to close the browser...")


if __name__ == "__main__":
    main()
