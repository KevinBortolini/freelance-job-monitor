"""Retained 99Freelas HTML and Freelancer.com digest strategies, made defensive."""
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
import re
from bs4 import BeautifulSoup
from .links import clean_url
from .models import Alert, Job, MonitorError, Parsed

MAX_TEXT = 30000

def read_eml(data: bytes) -> Alert:
    if len(data) > 2_000_000:
        raise MonitorError('Email fixture exceeds the supported size.')
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
        plain = []; html = []
        for part in message.walk():
            if part.is_multipart() or part.get_content_disposition() == 'attachment': continue
            if part.get_content_type() in {'text/plain', 'text/html'}:
                text = part.get_content()
                if isinstance(text, str):
                    (html if part.get_content_type() == 'text/html' else plain).append(text)
        return Alert(str(message.get('From', '')), str(message.get('Subject', '')), '\n'.join(plain), '\n'.join(html))
    except (LookupError, ValueError, TypeError):
        raise MonitorError('Email fixture has invalid MIME content.') from None

def platform_for_sender(sender: str, *, demo: bool = False) -> str | None:
    address = parseaddr(sender)[1]
    if address.count('@') != 1: return None
    domain = address.rsplit('@', 1)[-1].casefold()
    hosts = {'99Freelas':'99freelas.example', 'Freelancer.com':'freelancer.example'} if demo else {'99Freelas':'99freelas.com.br', 'Freelancer.com':'freelancer.com'}
    for name, host in hosts.items():
        if domain == host or domain.endswith('.' + host): return name
    return None

def _finish(job: Job, *, demo: bool) -> Parsed:
    if not job.title.strip(): return Parsed((), ('missing_title',))
    try: url = clean_url(job.link, job.platform, demo=demo)
    except MonitorError: return Parsed((), ('missing_or_invalid_link',))
    fields = [job.title, job.budget, job.skills, job.description, job.category, job.level]
    issues = []
    if any(len(x) > MAX_TEXT for x in fields): issues.append('truncated_field')
    fields = [x[:MAX_TEXT] for x in fields]
    if not job.budget: issues.append('missing_budget')
    if not job.description: issues.append('missing_description')
    return Parsed((Job(job.platform, fields[0], url, *fields[1:]),), tuple(issues))

def parse_99freelas(subject: str, body: str, *, demo: bool = False) -> Parsed:
    soup = BeautifulSoup(body, 'html.parser')
    project = None
    for a in soup.find_all('a', href=True):
        try:
            clean_url(a['href'], '99Freelas', demo=demo); project = a; break
        except MonitorError: continue
    if project is None: return Parsed((), ('unexpected_99freelas_template',))
    title = project.get_text(' ', strip=True)
    if not title:
        title = re.sub(r'^(?:New Project|Novo Projeto)\s*:\s*', '', subject, flags=re.I).strip() if re.match(r'^(?:New Project|Novo Projeto)\s*:', subject, flags=re.I) else ''
    category = level = budget = description = ''
    for p in soup.find_all('p'):
        text = p.get_text(' ', strip=True)
        if re.search(r'(?:Budget|Orçamento)\s*:', text, re.I):
            parts = [x.strip() for x in text.split('|')]
            if len(parts) >= 3:
                category, level = parts[:2]
                budget = re.sub(r'^(?:Budget|Orçamento)\s*:\s*', '', parts[2], flags=re.I)
            else:
                budget = re.sub(r'^.*?(?:Budget|Orçamento)\s*:\s*', '', text, flags=re.I)
        if re.match(r'^(?:Project|Projeto)\s*:', text, re.I):
            description = re.sub(r'^(?:Project|Projeto)\s*:\s*', '', text, flags=re.I)
            description = re.sub(r'(?:Read more\.?|Leia mais\.?)\s*$', '', description, flags=re.I).strip()
    return _finish(Job('99Freelas', title, project['href'], budget=budget, description=description, category=category, level=level), demo=demo)

def _html_digest(body: str) -> str:
    soup = BeautifulSoup(body, 'html.parser')
    for bad in soup(['script','style']): bad.decompose()
    for a in soup.find_all('a', href=True):
        a.replace_with(a.get_text(' ', strip=True) + '\n' + a['href'] + '\n')
    return soup.get_text('\n', strip=True)

def parse_freelancer(body: str, *, demo: bool = False) -> Parsed:
    # As in the source, a title immediately followed by Budget: starts a job.
    lines = [x.strip() for x in body.splitlines() if x.strip()]
    starts = [i for i in range(len(lines)-1) if lines[i+1].startswith('Budget:')]
    if not starts: return Parsed((), ('unexpected_freelancer_template',))
    jobs = []; issues = []
    for start, end in zip(starts, starts[1:] + [len(lines)]):
        budget = skills = link = ''; description = []; in_description = False
        for line in lines[start+1:end]:
            if line.startswith('Budget:'):
                budget = line.removeprefix('Budget:').strip(); in_description = False
            elif line.startswith('Skills:'):
                skills = line.removeprefix('Skills:').strip(); in_description = False
            elif line.startswith('Description:'):
                in_description = True
                if line.removeprefix('Description:').strip():description.append(line.removeprefix('Description:').strip())
            elif line.startswith(('https://','http://','/projects/')):
                try: link = clean_url(line, 'Freelancer.com', demo=demo)
                except MonitorError: pass
                in_description = False
            elif in_description: description.append(line)
        p = _finish(Job('Freelancer.com', lines[start], link, budget, skills, '\n'.join(description)), demo=demo)
        jobs.extend(p.jobs); issues.extend(p.issues)
    return Parsed(tuple(jobs), tuple(issues))

def parse_alert(alert: Alert, *, demo: bool = False) -> Parsed:
    platform = platform_for_sender(alert.sender, demo=demo)
    if platform == '99Freelas':return parse_99freelas(alert.subject, alert.html or alert.plain, demo=demo)
    if platform == 'Freelancer.com':return parse_freelancer(alert.plain or _html_digest(alert.html), demo=demo)
    return Parsed((), ('unsupported_sender',))
