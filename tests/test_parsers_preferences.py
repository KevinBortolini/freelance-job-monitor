from dataclasses import replace
from pathlib import Path
import pytest
from job_monitor.models import Alert,Job,MonitorError
from job_monitor.parsers import parse_alert,parse_99freelas,parse_freelancer,platform_for_sender,read_eml
from job_monitor.preferences import contains,parse_preferences,score_job
from job_monitor.links import clean_url,job_key

def test_invented_99_html_fixture(jobs):
    j=next(x for x in jobs if x.title=='Python CSV automation')
    assert j.platform=='99Freelas' and j.category=='Automation'
    assert j.budget=='BRL 1,200 fixed (fictional)'
    assert j.description=='Build an API export for invented order data.'
    assert 'utm_' not in j.link and 'project_id=DEMO-101' in j.link

def test_invented_freelancer_digest(jobs):
    found=[j for j in jobs if j.platform=='Freelancer.com']
    assert [j.title for j in found]==['Data cleaning helper','Spreadsheet automation','Unpaid trial API task']
    assert found[0].skills=='CSV, API' and found[0].description=='Clean an invented stock list.'

def test_99_subject_fallback_and_optional_missing_fields():
    p=parse_99freelas('New Project: Invented title','<a href="https://99freelas.example/project/fake"></a>',demo=True)
    assert p.jobs[0].title=='Invented title'
    assert set(p.issues)=={'missing_budget','missing_description'}

def test_original_portuguese_marker_support_without_real_records():
    p=parse_99freelas('Novo Projeto: Invented title','<a href="https://99freelas.example/project/fake"></a><p>Demo | Entry | Or\u00e7amento: BRL 10</p><p>Projeto: Invented example. Leia mais.</p>',demo=True)
    assert p.jobs[0].description=='Invented example.' and p.jobs[0].budget=='BRL 10'

@pytest.mark.parametrize('body',['','<p>Invented newsletter</p>','<a href="javascript:alert(1)">Invented</a>'])
def test_unexpected_99_templates(body):
    p=parse_99freelas('Invented',body,demo=True)
    assert not p.jobs and p.issues==('unexpected_99freelas_template',)

def test_missing_title_or_link():
    assert parse_99freelas('Unknown','<a href="https://99freelas.example/project/fake"></a>',demo=True).issues==('missing_title',)
    p=parse_freelancer('Invented\nBudget: USD 10\nSkills: CSV\nDescription:\nFirst line\nSecond line',demo=True)
    assert not p.jobs and p.issues==('missing_or_invalid_link',)

def test_plain_multiline_and_html_digest():
    body='Invented\nBudget: USD 10\nSkills: CSV\nDescription:\nFirst line\nSecond line\n/projects/fake?project_id=17'
    assert parse_freelancer(body,demo=True).jobs[0].description=='First line\nSecond line'
    alert=Alert('alerts@freelancer.example','Invented','', '<div>Invented</div><div>Budget: USD 10</div><div>Description:</div><p>Fictional text</p><a href="/projects/fake">View</a>')
    assert parse_alert(alert,demo=True).jobs[0].title=='Invented'

@pytest.mark.parametrize('sender',['alerts@freelancer.com.evil.example','alerts@notfreelancer.com','freelancer.com','alerts@99freelas.com.br.evil.example'])
def test_sender_domain_spoofing_rejected(sender):
    assert platform_for_sender(sender) is None

def test_nested_mime_prefers_html_for_99():
    data=b'From: alerts@99freelas.example\nSubject: New Project: Invented\nMIME-Version: 1.0\nContent-Type: multipart/alternative; boundary=x\n\n--x\nContent-Type: text/plain\n\nNo project in plain alternative\n--x\nContent-Type: text/html\n\n<a href="https://99freelas.example/project/fake">Invented</a>\n--x--\n'
    assert parse_alert(read_eml(data),demo=True).jobs[0].title=='Invented'

@pytest.mark.parametrize('text,term,expected',[
    ('PYTHON python python','python',True),('pythonic','python',False),
    ('pre_python','python',False),('Caf\u00e9 automation','cafe',True),
    ('data\n cleaning','DATA CLEANING',True),('data-cleaning','data cleaning',False),
    ('C++ helper','c++',True),('apiary','api',False),
])
def test_literal_case_accent_word_phrase_behavior(text,term,expected):assert contains(text,term)==expected

def test_independently_worked_demo_scores(jobs,prefs):
    scores={j.title:score_job(j,prefs) for j in jobs}
    assert scores['Python CSV automation'].score==68 # 20+10+8+6+15+9
    assert scores['Data cleaning helper'].score==30 # 7+6+8+9
    assert scores['Spreadsheet automation'].score==12 # 4+10, capped at 12
    assert scores['Unpaid trial API task'].excluded and scores['Unpaid trial API task'].score==0
    assert scores['Documentation checklist'].match=='Discarded'
    assert '+20 weight line' in scores['Python CSV automation'].explanation
    assert 'raw 68; final 68' in scores['Python CSV automation'].explanation

def test_repeated_terms_count_once_and_budget_url_do_not_score(prefs):
    j=Job('99Freelas','python python','https://99freelas.example/project/python',budget='automation csv api')
    assert score_job(j,prefs).score==20
    assert score_job(replace(j,title='Invented'),prefs).score==0

def test_phrase_not_cross_field_but_combo_can(prefs):
    j=Job('99Freelas','data','https://99freelas.example/project/fake',description='cleaning')
    assert score_job(j,prefs).score==0
    j=replace(j,title='Python',description='automation')
    assert score_job(j,prefs).score==45 # two weights plus all-term combo

@pytest.mark.parametrize('bad',[
    'unknown = 10','weight = nope | python','weight = 0 | python','weight = 10 |',
    'weight = 10 | cafe; CAF\u00c9','pair = 2 | python','cap = 101 | csv || api',
    'exclude = python; api','weight = 10 | python # inline comment',
    'score_max = 100','__import__("os").system("echo unsafe")',
])
def test_invalid_preferences_have_line_numbers(bad):
    base='score_min=0\nscore_max=100\nconsider_score=1\ngood_score=15\nstrong_score=30\n'
    # Inline # is rejected rather than accidentally becoming a preference term.
    if ' # ' in bad:
        with pytest.raises(MonitorError,match=r'Preferences line 6:'):parse_preferences(base+bad)
    else:
        with pytest.raises(MonitorError,match=r'Preferences line \d+:'):parse_preferences(base+bad)

def test_duplicate_normalized_rule_and_threshold_order():
    base='score_min=0\nscore_max=100\nconsider_score=1\ngood_score=15\nstrong_score=30\n'
    with pytest.raises(MonitorError,match='Duplicate normalized rule'):parse_preferences(base+'weight=5|Cafe\nweight=7|CAF\u00c9')
    with pytest.raises(MonitorError):parse_preferences(base.replace('good_score=15','good_score=0')+'exclude=Invented')

def test_link_tracking_removed_identifiers_encoding_order_preserved():
    a='https://www.freelancer.com/projects/Fictional?id=A%2FB&sig=ab%2Bcd&utm_source=demo&v=17#details'
    assert clean_url(a,'Freelancer.com')=='https://freelancer.com/projects/Fictional?id=A%2FB&sig=ab%2Bcd&v=17'
    assert job_key('Freelancer.com',a)!=job_key('Freelancer.com',a.replace('v=17','v=18'))

@pytest.mark.parametrize('url',['javascript:alert(1)','http://freelancer.com/projects/x','https://freelancer.com.evil.example/projects/x','https://reader:password@freelancer.com/projects/x','https://freelancer.com:444/projects/x','https://freelancer.com/projects/','https://freelancer.com/projects/a\nb'])
def test_unsafe_urls_rejected(url):
    with pytest.raises(MonitorError):clean_url(url,'Freelancer.com')

def test_demo_and_live_links_separate():
    with pytest.raises(MonitorError):clean_url('https://freelancer.example/projects/x','Freelancer.com')
    assert clean_url('/projects/x?project_id=DEMO-1','Freelancer.com',demo=True)=='https://freelancer.example/projects/x?project_id=DEMO-1'
