from __future__ import annotations
import subprocess,sys
from datetime import datetime
from pathlib import Path
from .config import SYSTEM_ROOT


def main():
    log_dir=SYSTEM_ROOT/'logs'; log_dir.mkdir(parents=True,exist_ok=True)
    log=log_dir/f'update_{datetime.now():%Y%m%d_%H%M%S}.log'
    cmd=[sys.executable,'-m','paper_monitor_system.app.local_update',*sys.argv[1:]]
    print(f'Log: {log}')
    with log.open('w',encoding='utf-8') as f:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line,end=''); f.write(line); f.flush()
        code=proc.wait()
    raise SystemExit(code)

if __name__=='__main__': main()
