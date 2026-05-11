"""
Scheduled crawler wrapper — invoked by launchd on the crawler-Mac.

For each job:
    1. start_run(job_name)
    2. spawn the actual crawler subprocess with CRAWLER_UNATTENDED=1
    3. parse its exit code + tail of stdout for success/fail counts
    4. finish_run(...)

Usage:
    python3 run_scheduled.py market_discovery
    python3 run_scheduled.py internal_sweep
    python3 run_scheduled.py keyword_rank

Env vars (loaded from ~/.etseemate-crawler.env via launchd EnvironmentVariables):
    DATABASE_URL                  — Neon connection string
    CHROME_PATH                   — /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
    CRAWLER_NOTIFY_*              — email config for captcha alerts
    CRAWLER_UNATTENDED=1          — forces no-TTY mode in the crawler children
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from crawl_ledger import start_run, finish_run

HERE = Path(__file__).resolve().parent

JOBS = {
    "market_discovery": [sys.executable, str(HERE / "market_batch_scraper.py"), "--auto", "30"],
    "internal_sweep":   [sys.executable, str(HERE / "internal_listing_crawler.py"), "--auto"],
    "keyword_rank":     [sys.executable, str(HERE / "keyword_rank_crawler.py"), "--auto"],
}


def _parse_counts(output: str) -> tuple[int | None, int | None]:
    """Best-effort: scan tail of stdout for 'ok=N fail=N' style counters."""
    ok_m = re.search(r"(?:success|ok)[=: ]+(\d+)", output, re.IGNORECASE)
    fail_m = re.search(r"(?:fail|error)[=: ]+(\d+)", output, re.IGNORECASE)
    return (int(ok_m.group(1)) if ok_m else None,
            int(fail_m.group(1)) if fail_m else None)


def main(job: str) -> int:
    if job not in JOBS:
        print(f"Unknown job '{job}'. Options: {', '.join(JOBS)}")
        return 2

    run_id = start_run(job, metadata={"argv": JOBS[job]})
    env = os.environ.copy()
    env["CRAWLER_UNATTENDED"] = "1"

    print(f"[run_scheduled] job={job} run_id={run_id} starting", flush=True)
    t0 = time.time()
    try:
        proc = subprocess.run(
            JOBS[job], env=env, capture_output=True, text=True, timeout=4 * 3600
        )
        rc = proc.returncode
        tail = (proc.stdout or "")[-4000:] + "\n--STDERR--\n" + (proc.stderr or "")[-2000:]
        ok, fail = _parse_counts(tail)
        status = "success" if rc == 0 else ("partial" if (ok or 0) > 0 else "failed")
        err_summary = None if rc == 0 else f"exit={rc}\n{(proc.stderr or '')[-1500:]}"
        finish_run(run_id, status, success_count=ok, fail_count=fail, error_summary=err_summary)
        print(f"[run_scheduled] job={job} run_id={run_id} done status={status} "
              f"duration={time.time()-t0:.0f}s ok={ok} fail={fail}", flush=True)
        return rc
    except subprocess.TimeoutExpired:
        finish_run(run_id, "failed", error_summary="timeout after 4h")
        return 124
    except Exception as e:
        finish_run(run_id, "failed", error_summary=repr(e))
        raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
