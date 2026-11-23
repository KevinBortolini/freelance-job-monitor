"""Styled, idempotent Excel output with safe text and atomic replacement."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from .links import clean_url, job_key
from .models import Job, MonitorError, RunResult
from .paths import project_path
from .preferences import Preferences, score_job

HEADERS = ('First seen (UTC)','Platform','Title','Score','Match','Budget (as emailed)',
           'Skills / category','Description','Score explanation','Link','Status','Applied (YYYY-MM-DD)','Notes','Key')
SHEETS = ('Latest run','Opportunities','Discarded')
STATUSES = ('New','Review','To apply','Applied','Discarded')

def _hash(path):
    return sha256(path.read_bytes()).hexdigest() if path.exists() else None

@contextmanager
def output_lock(path: Path):
    lock = path.with_name(path.name + '.lock')
    fd = None
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(fd, str(os.getpid()).encode())
        yield
    except FileExistsError:
        raise MonitorError('Output is locked by another run or a stale monitor lock. Close other runs; inspect the lock locally before removing it.') from None
    finally:
        if fd is not None:
            os.close(fd); lock.unlink(missing_ok=True)

def _load(path: Path, mode: str):
    if not path.exists(): return [], [], []
    try:
        with path.open('rb') as f: wb = load_workbook(f)
        if wb.properties.identifier != 'freelance-job-monitor:' + mode + ':v1':
            raise MonitorError('Existing workbook is not this mode\'s monitor output; choose a new output file.')
        if tuple(wb.sheetnames) != SHEETS or any(tuple(c.value for c in wb[s][1]) != HEADERS for s in SHEETS):
            raise MonitorError('Existing workbook structure changed; preserve it and choose a new output file.')
        return [list(row) for row in wb['Opportunities'].iter_rows(min_row=2,values_only=True)], [list(row) for row in wb['Discarded'].iter_rows(min_row=2,values_only=True)], [list(row) for row in wb['Latest run'].iter_rows(min_row=2,values_only=True)]
    except MonitorError: raise
    except Exception:
        raise MonitorError('Cannot read the existing workbook. Close Excel and check the file locally; it has not been overwritten.') from None

def _style(sheet, rows):
    sheet.append(HEADERS)
    for values in rows: sheet.append(values)
    widths = [22,18,43,9,13,25,30,65,85,45,15,22,38,20]
    for i,width in enumerate(widths,1):sheet.column_dimensions[chr(64+i)].width=width
    sheet.column_dimensions['N'].hidden = True
    for row in sheet:
        for cell in row:
            if isinstance(cell.value,str):
                # Explicit string type defeats formula inference without changing the value.
                cell.value = ''.join(c if ord(c)>=32 or c in '\n\r\t' else '\ufffd' for c in cell.value)
                if len(cell.value)>32767:raise MonitorError('A workbook field exceeds Excel\'s text limit; existing output is unchanged.')
                cell.data_type = 's'
            cell.alignment=Alignment(vertical='top',wrap_text=True)
    for cell in sheet[1]:
        cell.fill=PatternFill('solid',fgColor='173D55');cell.font=Font(color='FFFFFF',bold=True)
    sheet.row_dimensions[1].height=32
    for row in range(2,sheet.max_row+1):
        sheet.row_dimensions[row].height=72
        fill='F0F6FA' if row%2==0 else 'FFFFFF'
        for cell in sheet[row]:cell.fill=PatternFill('solid',fgColor=fill)
        score=sheet.cell(row,4);score.font=Font(bold=True,color='176B45' if sheet.cell(row,5).value in {'Strong','Good'} else '6E5860')
        link=sheet.cell(row,10)
        if link.value:
            link.hyperlink=link.value;link.font=Font(color='0563C1',underline='single')
        sheet.cell(row,1).number_format='yyyy-mm-dd hh:mm'
        sheet.cell(row,12).number_format='yyyy-mm-dd'
    validation=DataValidation(type='list',formula1='"'+','.join(STATUSES)+'"',allow_blank=True)
    sheet.add_data_validation(validation);validation.add('K2:K1048576')
    sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
    sheet.sheet_view.zoomScale=85

def _build(opportunities,discarded,latest,mode,now):
    wb=Workbook();wb.remove(wb.active)
    wb.properties.creator='Fictional demonstration' if mode=='demo' else 'Freelance Job Monitor'
    wb.properties.identifier='freelance-job-monitor:'+mode+':v1'
    wb.properties.title='Fictional opportunity demonstration' if mode=='demo' else 'Local opportunity monitor'
    wb.properties.created=now.replace(tzinfo=None);wb.properties.modified=now.replace(tzinfo=None)
    for name,rows in zip(SHEETS,(latest,opportunities,discarded)):_style(wb.create_sheet(name),rows)
    return wb

def save_jobs(jobs: list[Job], prefs: Preferences, output: Path, *, mode: str, now=None) -> RunResult:
    output=project_path(output)
    if output.suffix.lower()!='.xlsx' or mode not in {'demo','live'}:
        raise MonitorError('Choose an .xlsx output file and a supported mode.')
    now=now or datetime.now(timezone.utc)
    temp=None
    try:
        output.parent.mkdir(parents=True,exist_ok=True)
        with output_lock(output):
            if output.with_name('~$'+output.name).exists():
                raise MonitorError('Excel has an owner file for this workbook. Close it before running again.')
            before=_hash(output)
            opportunities,discarded,previous_latest=_load(output,mode)
            existing=set()
            for row in opportunities+discarded:
                if len(row)!=len(HEADERS) or not isinstance(row[3],(int,float)) or isinstance(row[3],bool):
                    raise MonitorError('Existing workbook has an invalid data row; no replacement made.')
                key=job_key(row[1],row[9],demo=mode=='demo')
                if row[13]!=key or key in existing:
                    raise MonitorError('Existing workbook keys are inconsistent; preserve it and choose a new output file.')
                existing.add(key)
            latest=[];added=discarded_count=duplicates=0
            for job in jobs:
                key=job_key(job.platform,job.link,demo=mode=='demo')
                if key in existing:
                    duplicates+=1;continue
                scoring=score_job(job,prefs)
                reject=scoring.excluded or scoring.match=='Discarded'
                row=[now.replace(tzinfo=None),job.platform,job.title,scoring.score,scoring.match,job.budget,
                     '; '.join(x for x in (job.skills,job.category,job.level) if x),job.description,
                     scoring.explanation,clean_url(job.link,job.platform,demo=mode=='demo'),
                     'Discarded' if reject else 'New',None,'',key]
                (discarded if reject else opportunities).append(row);latest.append(row);existing.add(key)
                if reject:discarded_count+=1
                else:added+=1
            sort=lambda row:(-row[3],row[1],row[13])
            opportunities.sort(key=sort);discarded.sort(key=sort);latest.sort(key=sort)
            wb=_build(opportunities,discarded,latest or previous_latest,mode,now)
            with NamedTemporaryFile(dir=output.parent,prefix='.monitor-',suffix='.xlsx',delete=False) as f:
                temp=Path(f.name)
            wb.save(temp)
            # Validate the ZIP/workbook before replacement; never edit the existing file in place.
            with temp.open('rb') as f:
                check=load_workbook(f);assert tuple(check.sheetnames)==SHEETS;check.close()
            # Windows _commit (used by os.fsync) requires a writable handle.
            with temp.open('r+b') as f:os.fsync(f.fileno())
            if _hash(output)!=before:
                raise MonitorError('Workbook changed during this run; no replacement made. Retry after closing other editors.')
            os.replace(temp,output);temp=None
            return RunResult(added,discarded_count,duplicates)
    except MonitorError: raise
    except Exception:
        raise MonitorError('Cannot write the workbook. Close Excel, check permissions/free space, and retry. Existing output was not edited in place.') from None
    finally:
        if temp is not None:temp.unlink(missing_ok=True)
