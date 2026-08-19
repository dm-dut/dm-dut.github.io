from __future__ import annotations
import argparse,subprocess,sys,tempfile,shutil
from pathlib import Path
from .config import BUILD_ID,DB_PATH,REPO_ROOT,WEB_JSON_PATH


def run(cmd:list[str],check=True):
    print('-', ' '.join(cmd))
    return subprocess.run(cmd,cwd=str(REPO_ROOT),check=check,text=True)


def clean_repo():
    p=subprocess.run(['git','status','--porcelain'],cwd=str(REPO_ROOT),capture_output=True,text=True,check=True)
    dirty=[line for line in p.stdout.splitlines() if line.strip() and 'RESET_TO_V4.flag' not in line]
    if dirty: raise SystemExit('Git working tree has uncommitted changes. Commit/stash them first.\n'+'\n'.join(dirty))


def branch():
    p=subprocess.run(['git','rev-parse','--abbrev-ref','HEAD'],cwd=str(REPO_ROOT),capture_output=True,text=True,check=True)
    return p.stdout.strip()


def publish(b:str):
    if not DB_PATH.exists() or not WEB_JSON_PATH.exists(): raise SystemExit('Generated DB/JSON missing.')
    run(['git','add','-A',str(DB_PATH.relative_to(REPO_ROOT)),str(WEB_JSON_PATH.relative_to(REPO_ROOT)),'paper_monitor_system/data/RESET_TO_V4.flag'])
    d=subprocess.run(['git','diff','--cached','--quiet'],cwd=str(REPO_ROOT))
    if d.returncode==0:
        print('No paper-monitor data changes to commit.'); return
    run(['git','commit','-m','chore: update paper monitor'])
    run(['git','push','origin',b])
    print('Paper-monitor data pushed successfully.')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--provider',choices=['all','sciencedirect','springer','ieee'],default='all')
    ap.add_argument('--initial-days',type=int,default=2)
    ap.add_argument('--no-git',action='store_true')
    ap.add_argument('--no-push',action='store_true')
    ap.add_argument('--skip-tests',action='store_true')
    args=ap.parse_args()
    print(f'Paper Monitor Build: {BUILD_ID}')
    print(f'Repository: {REPO_ROOT}')
    b=''
    if not args.no_git:
        clean_repo(); b=branch(); run(['git','pull','--ff-only','origin',b])
    if not args.skip_tests:
        run([sys.executable,'-m','paper_monitor_system.app.selfcheck'])
        run([sys.executable,'-m','paper_monitor_system.app.selftest'])
    run([sys.executable,'-m','paper_monitor_system.app.sync','--provider',args.provider,'--initial-days',str(args.initial_days)])
    if args.no_git: print('Fetch/export complete; git skipped.')
    elif args.no_push: print('Fetch/export complete; generated files left uncommitted.')
    else: publish(b)

if __name__=='__main__': main()
