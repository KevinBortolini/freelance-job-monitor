from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import json
import pytest
from openpyxl import load_workbook,Workbook
from job_monitor.models import Job,MonitorError
from job_monitor.paths import ROOT,project_path,private_path
from job_monitor.workbook import save_jobs,HEADERS,SHEETS,output_lock

def test_dedup_within_across_runs_formatting_explanations(tmp_path,jobs,prefs):
    out=tmp_path/'demo.xlsx';now=datetime(2026,1,15,12,tzinfo=timezone.utc)
    result=save_jobs(jobs,prefs,out,mode='demo',now=now)
    assert (result.added,result.discarded,result.duplicates)==(3,2,1)
    wb=load_workbook(out);assert tuple(wb.sheetnames)==SHEETS
    assert wb['Opportunities'].max_row==4 and wb['Discarded'].max_row==3
    assert wb['Latest run'].max_row==6
    for name in SHEETS:
        sheet=wb[name];assert tuple(c.value for c in sheet[1])==HEADERS
        assert sheet.freeze_panes=='A2' and sheet.auto_filter.ref==sheet.dimensions
        assert sheet['A1'].fill.fgColor.rgb.endswith('173D55')
        assert sheet.column_dimensions['N'].hidden and sheet.data_validations.count==1
    row=next(row for row in wb['Opportunities'].iter_rows(min_row=2) if row[2].value=='Python CSV automation')
    assert row[3].value==68 and 'raw 68; final 68' in row[8].value
    assert row[9].hyperlink.target==row[9].value
    # Human review fields survive a new run and sorting.
    wb['Opportunities']['K2']='Review';wb['Opportunities']['M2']='Invented local note';wb.save(out)
    again=save_jobs(jobs,prefs,out,mode='demo',now=now)
    assert (again.added,again.discarded,again.duplicates)==(0,0,6)
    wb=load_workbook(out);assert wb['Opportunities']['K2'].value=='Review'
    assert wb['Opportunities']['M2'].value=='Invented local note'
    assert wb['Latest run'].max_row==6 # last batch with additions is retained

def test_ties_are_deterministic_not_arrival_order(tmp_path,prefs):
    a=Job('Freelancer.com','Python','https://freelancer.example/projects/a')
    b=replace(a,link='https://freelancer.example/projects/b')
    out=tmp_path/'ties.xlsx';save_jobs([b,a],prefs,out,mode='demo')
    wb=load_workbook(out)
    assert [r[9] for r in wb['Opportunities'].iter_rows(min_row=2,values_only=True)]==[a.link,b.link]

@pytest.mark.parametrize('text',['=1+1','+SUM(1,2)','-2+3','@SUM(1,2)','\t=1+1'])
def test_untrusted_text_is_literal_not_formula(tmp_path,prefs,text):
    j=Job('99Freelas',text,'https://99freelas.example/project/invented',description='Python')
    out=tmp_path/'safe.xlsx';save_jobs([j],prefs,out,mode='demo')
    wb=load_workbook(out);assert wb['Opportunities']['C2'].value==text
    assert wb['Opportunities']['C2'].data_type=='s'
    assert not any(c.data_type=='f' for s in wb for row in s for c in row)

@pytest.mark.parametrize('failure',['replace','save','sync','external_change'])
def test_failed_write_preserves_existing_bytes(tmp_path,jobs,prefs,monkeypatch,failure):
    import job_monitor.workbook as module
    out=tmp_path/'preserved.xlsx';save_jobs(jobs,prefs,out,mode='demo');before=out.read_bytes()
    if failure=='replace':
        def fail(*a,**kw):raise PermissionError('Simulated locked workbook private details')
        monkeypatch.setattr(module.os,'replace',fail)
    elif failure=='save':
        def fail(*a,**kw):raise OSError('Simulated disk write failure private details')
        monkeypatch.setattr(module.Workbook,'save',fail)
    elif failure=='sync':
        def fail(*a,**kw):raise OSError('Simulated flush failure private details')
        monkeypatch.setattr(module.os,'fsync',fail)
    else:
        real=module._hash;calls=0
        def changed(path):
            nonlocal calls
            calls+=1
            return real(path) if calls==1 else 'changed-in-another-editor'
        monkeypatch.setattr(module,'_hash',changed)
    with pytest.raises(MonitorError) as error:save_jobs(jobs,prefs,out,mode='demo')
    assert 'private details' not in str(error.value)
    assert out.read_bytes()==before
    assert not list(tmp_path.glob('.monitor-*')) and not out.with_name(out.name+'.lock').exists()

def test_monitor_lock_and_excel_owner_file(tmp_path,jobs,prefs):
    out=tmp_path/'locked.xlsx'
    with output_lock(out):
        with pytest.raises(MonitorError,match='locked'):save_jobs(jobs,prefs,out,mode='demo')
    owner=tmp_path/'~$locked.xlsx';owner.write_text('fictional owner marker')
    with pytest.raises(MonitorError,match='owner file'):save_jobs(jobs,prefs,out,mode='demo')
    assert not out.exists()

def test_foreign_or_cross_mode_workbook_not_overwritten(tmp_path,jobs,prefs):
    out=tmp_path/'foreign.xlsx';Workbook().save(out);before=out.read_bytes()
    with pytest.raises(MonitorError,match='not this mode'):save_jobs(jobs,prefs,out,mode='demo')
    assert out.read_bytes()==before
    out.unlink();save_jobs(jobs,prefs,out,mode='demo');before=out.read_bytes()
    with pytest.raises(MonitorError,match='not this mode'):save_jobs([],prefs,out,mode='live')
    assert out.read_bytes()==before

def test_missing_preferences_and_paths_fail_safely(tmp_path,capsys):
    from job_monitor.__main__ import main
    assert main(['demo','--preferences',str(tmp_path/'missing.txt')])==2
    assert 'Cannot read' in capsys.readouterr().out
    with pytest.raises(MonitorError):project_path(ROOT.parent/'outside-project'/'private.xlsx')
    with pytest.raises(MonitorError):private_path('artifacts/not-private.json')

def test_cli_offline_works_with_network_and_google_imports_blocked(tmp_path):
    out=tmp_path/'offline.xlsx'
    code='''
import socket, builtins, sys
def blocked(*a,**k):raise AssertionError('Offline mode attempted network access')
socket.socket.connect=blocked;socket.create_connection=blocked
original=builtins.__import__
def guarded(name,*a,**k):
    if name.startswith(('google','googleapiclient')):raise AssertionError('Offline mode imported Gmail SDK')
    return original(name,*a,**k)
builtins.__import__=guarded
from job_monitor.__main__ import main
raise SystemExit(main(sys.argv[1:]))
'''
    args=[sys.executable,'-c',code,'demo','--preferences','preferences.example.txt','--output',str(out)]
    first=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
    assert first.returncode==0,first.stderr+first.stdout
    assert '3 new opportunities; 2 new discarded/excluded; 1 duplicates' in first.stdout
    second=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
    assert second.returncode==0 and '6 duplicates' in second.stdout
    assert not any(x in first.stdout for x in ['reader@example.test','invented-python','Python CSV'])

def test_preferences_changes_do_not_silently_rescore_history(tmp_path,jobs,prefs):
    out=tmp_path/'history.xlsx';save_jobs(jobs,prefs,out,mode='demo')
    from dataclasses import replace
    save_jobs(jobs,replace(prefs,rules=()),out,mode='demo')
    assert load_workbook(out)['Opportunities']['D2'].value==68


def test_file_sync_uses_writable_handle_for_windows(tmp_path,jobs,prefs,monkeypatch):
    import job_monitor.workbook as module
    real_sync=module.os.fsync
    calls=[]
    def windows_compatible_sync(fd):
        # Windows _commit requires a writable descriptor. A zero-byte write
        # checks that contract on Linux too without modifying the workbook.
        module.os.write(fd,b'')
        calls.append(fd)
        real_sync(fd)
    monkeypatch.setattr(module.os,'fsync',windows_compatible_sync)
    out=tmp_path/'windows-sync.xlsx'
    result=save_jobs(jobs,prefs,out,mode='demo')
    assert result.added==3 and len(calls)==1
    assert load_workbook(out)['Opportunities'].max_row==4
