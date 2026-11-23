"""Explicit demo/live CLI; no implicit OAuth, personal defaults or task scheduler."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from .models import MonitorError
from .paths import ROOT, project_path
from .preferences import load_preferences
from .parsers import read_eml, parse_alert
from .workbook import save_jobs

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description='Rank freelance email alerts into a safe local Excel workbook.')
    modes=parser.add_subparsers(dest='mode',required=True)
    demo=modes.add_parser('demo',help='Offline invented email fixtures; no OAuth or network access.')
    demo.add_argument('--preferences',required=True,help='Editable TXT preferences, e.g. preferences.example.txt.')
    demo.add_argument('--output',default='artifacts/demo.xlsx')
    live=modes.add_parser('live',help='Explicitly read your own Gmail account; requires separate setup.')
    live.add_argument('--preferences',required=True)
    live.add_argument('--settings',required=True,help='Your ignored live TOML configuration.')
    live.add_argument('--authorize',action='store_true',help='Allow first interactive authorization if no local token exists.')
    args=parser.parse_args(argv)
    try:
        prefs=load_preferences(project_path(args.preferences));issues=Counter();jobs=[];messages=0
        if args.mode=='demo':
            pairs=[]
            for path in sorted((ROOT/'tests/fixtures').glob('*.eml')):
                try:pairs.append((read_eml(path.read_bytes()),None))
                except (OSError,MonitorError):pairs.append((None,'malformed_email'))
            if not pairs:raise MonitorError('Offline fixtures are missing; restore the reviewed repository examples.')
            output=project_path(args.output);now=datetime(2026,1,15,12,tzinfo=timezone.utc)
        else:
            from .gmail import load_settings,create_service,iter_alerts
            settings=load_settings(project_path(args.settings));service=create_service(settings,authorize=args.authorize)
            pairs=iter_alerts(service,settings);output=settings.output_file;now=None
        for alert,issue in pairs:
            if issue:issues[issue]+=1
            if alert is None:continue
            messages+=1;parsed=parse_alert(alert,demo=args.mode=='demo');jobs.extend(parsed.jobs);issues.update(parsed.issues)
        result=save_jobs(jobs,prefs,output,mode=args.mode,now=now)
        print(f'{args.mode.capitalize()} complete: {messages} emails processed; {result.added} new opportunities; {result.discarded} new discarded/excluded; {result.duplicates} duplicates skipped.')
        print('Workbook saved at the selected output path. Latest run retains the last batch of new rows when a rerun adds nothing.')
        for code,count in sorted(issues.items()):print(f'Notice: {code} ({count}). See the manual for next steps.')
        return 0
    except MonitorError as error:
        print(f'Error: {error}');return 2
    except Exception:
        print('Error: Unexpected local processing failure. No email/credential details are printed; preserve output and consult safe troubleshooting.');return 2

if __name__=='__main__':raise SystemExit(main())
