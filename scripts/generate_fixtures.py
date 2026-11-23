"""Generate invented email messages, never copies of a mailbox/template export."""
from email.message import EmailMessage
from email import policy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def envelope(name,subject,body,subtype,platform):
    message=EmailMessage()
    message['From']=f'Invented alerts <alerts@{platform}.example>'
    message['To']='Demo reader <reader@example.test>'
    message['Date']='Thu, 15 Jan 2026 12:00:00 +0000'
    message['Message-ID']=f'<invented-{name}@example.test>'
    message['Subject']=subject
    message.set_content(body,subtype=subtype,charset='utf-8')
    return message.as_bytes(policy=policy.SMTP)

def fixtures():
    python='''<html><body><h1>Invented project alert</h1>
<a href="https://99freelas.example/project/invented-python-import?project_id=DEMO-101&amp;utm_source=fictional-email">Python CSV automation</a>
<p>Automation | Intermediate | Budget: BRL 1,200 fixed (fictional)</p>
<p>Project: Build an API export for invented order data. Read more.</p></body></html>'''
    digest='''Invented Freelancer.com opportunities

Data cleaning helper
Budget: USD 200 fixed (fictional)
Skills: CSV, API
Description:
Clean an invented stock list.
/projects/invented-data-cleaning?project_id=DEMO-202&utm_source=demo

Spreadsheet automation
Budget: USD 150 fixed (fictional)
Skills: Spreadsheet
Description:
Organize a fictional worksheet.
/projects/invented-spreadsheet?project_id=DEMO-203

Unpaid trial API task
Budget: Unpaid (fictional exclusion example)
Skills: Python
Description:
Fictional rejected example. No work is offered.
/projects/invented-trial?project_id=DEMO-204
'''
    documentation='''<html><body><a href="https://99freelas.example/project/invented-checklist?project_id=DEMO-105">Documentation checklist</a>
<p>Operations | Entry | Budget: BRL 100 fixed (fictional)</p>
<p>Project: Write process steps for an invented office.</p></body></html>'''
    return {
        '99-python.eml':envelope('python','New Project: Python CSV automation',python,'html','99freelas'),
        '99-duplicate.eml':envelope('duplicate','New Project: Python CSV automation',python.replace('fictional-email','another-fictional-email'),'html','99freelas'),
        '99-documentation.eml':envelope('documentation','New Project: Documentation checklist',documentation,'html','99freelas'),
        'freelancer-digest.eml':envelope('digest','Invented project digest',digest,'plain','freelancer'),
    }

if __name__=='__main__':
    directory=ROOT/'tests/fixtures';directory.mkdir(parents=True,exist_ok=True)
    for name,data in fixtures().items():
        p=directory/name
        if p.exists():
            if p.read_bytes()!=data:raise SystemExit('An existing fixture differs; no file was overwritten.')
        else:
            with p.open('xb') as f:f.write(data)
    print('Four invented fixtures generated/verified without overwriting changed files.')
