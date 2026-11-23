"""Validated text preferences: escaped literal matches, never executable content."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import unicodedata
from .models import Job, MonitorError, Scored

def normalize(text: str) -> str:
    folded = unicodedata.normalize('NFKD', text.casefold())
    return re.sub(r'\s+', ' ', ''.join(c for c in folded if not unicodedata.combining(c))).strip()

def contains(text: str, phrase: str) -> bool:
    pattern = r'(?<!\w)' + re.escape(normalize(phrase)).replace(r'\ ', r'\s+') + r'(?!\w)'
    return re.search(pattern, normalize(text)) is not None

@dataclass(frozen=True)
class Rule:
    kind: str
    points: int
    first: tuple[str, ...]
    second: tuple[str, ...] = ()
    line: int = 0

@dataclass(frozen=True)
class Preferences:
    minimum: int
    maximum: int
    consider: int
    good: int
    strong: int
    rules: tuple[Rule, ...]
    fingerprint: str

def parse_preferences(text: str) -> Preferences:
    settings = {}; rules = []; seen = set()
    keys = {'score_min', 'score_max', 'consider_score', 'good_score', 'strong_score'}
    def error(line, message):
        raise MonitorError(f'Preferences line {line}: {message}')
    def terms(value, line):
        group = tuple(part.strip() for part in value.split(';'))
        if not group or any(not x or len(x) > 120 or not any(c.isalnum() for c in x) for x in group):
            error(line, 'Use nonempty literal words/phrases of at most 120 characters, separated by semicolons.')
        if len({normalize(x) for x in group}) != len(group):
            error(line, 'Duplicate normalized term in a group.')
        return group
    if len(text.encode('utf-8')) > 65536:
        error(1, 'Configuration exceeds 64 KiB.')
    for line, raw in enumerate(text.splitlines(), 1):
        value = raw.strip()
        if not value or value.startswith('#'):
            continue
        if '=' not in value:
            error(line, 'Expected setting = value; comments occupy their own lines.')
        key, value = (part.strip() for part in value.split('=', 1))
        if re.search(r'\s+#', value):
            error(line, 'Inline comments are not supported; put comments on their own lines. C# remains a literal term.')
        if key in keys:
            if key in settings:
                error(line, 'Duplicate numeric setting.')
            if not re.fullmatch(r'-?\d{1,5}', value):
                error(line, 'Expected an integer, without comments or trailing text.')
            settings[key] = (int(value), line)
            continue
        if key not in {'weight', 'all', 'pair', 'cap', 'exclude'}:
            error(line, 'Unknown setting or rule type.')
        points = 0
        if key != 'exclude':
            if value.count('|') < 1:
                error(line, 'Expected integer points | term(s).')
            number, value = (x.strip() for x in value.split('|', 1))
            if not re.fullmatch(r'-?\d{1,4}', number):
                error(line, 'Rule points must be integers between -9999 and 9999.')
            points = int(number)
            if key != 'cap' and points == 0:
                error(line, 'A scoring rule cannot have zero weight.')
        if key in {'pair', 'cap'}:
            if value.count('||') != 1:
                error(line, 'Expected first group || second group.')
            a, b = value.split('||')
            first, second = terms(a, line), terms(b, line)
        else:
            if '|' in value:
                error(line, 'Unexpected pipe separator.')
            first, second = terms(value, line), ()
            if key in {'weight', 'exclude'} and len(first) != 1:
                error(line, 'This rule accepts exactly one word/phrase.')
        identity = (key, tuple(map(normalize, first)), tuple(map(normalize, second)))
        if identity in seen:
            error(line, 'Duplicate normalized rule; consolidate its weight.')
        seen.add(identity); rules.append(Rule(key, points, first, second, line))
        if len(rules) > 200:
            error(line, 'At most 200 rules are supported.')
    if set(settings) != keys:
        error(len(text.splitlines()) + 1, 'All five numeric settings are required: score_min, score_max, consider_score, good_score, strong_score.')
    lo, hi, consider, good, strong = (settings[k][0] for k in ['score_min','score_max','consider_score','good_score','strong_score'])
    if not 0 <= lo < consider < good < strong <= hi <= 10000:
        error(settings['strong_score'][1], 'Require 0 <= score_min < consider_score < good_score < strong_score <= score_max <= 10000.')
    for rule in rules:
        if rule.kind == 'cap' and not lo <= rule.points <= hi:
            error(rule.line, 'Cap must be inside the score range.')
    if not rules:
        error(1, 'Add at least one scoring or exclusion rule.')
    return Preferences(lo, hi, consider, good, strong, tuple(rules), sha256(text.encode()).hexdigest()[:12])

def load_preferences(path: Path) -> Preferences:
    try:
        return parse_preferences(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError):
        raise MonitorError('Cannot read the preferences file as UTF-8. Copy the example explicitly; existing configuration is never overwritten.') from None

def score_job(job: Job, prefs: Preferences) -> Scored:
    fields = job.search_fields
    def hit(term):
        return any(contains(field, term) for field in fields)
    score = 0; reasons = []; caps = []; exclusions = []
    for r in prefs.rules:
        first = [term for term in r.first if hit(term)]
        second = [term for term in r.second if hit(term)]
        matches = (len(first) == len(r.first) if r.kind == 'all' else bool(first))
        if r.kind == 'pair': matches = bool(first and second)
        if r.kind == 'cap': matches = bool(first and not second)
        if not matches: continue
        detail = ', '.join(first + (second if r.kind == 'pair' else []))
        if r.kind == 'exclude':
            exclusions.append(f'EXCLUDE line {r.line}: {detail}')
        elif r.kind == 'cap':
            caps.append(r.points); reasons.append(f'CAP {r.points} line {r.line}: {detail}; no second-group match')
        else:
            score += r.points; reasons.append(f'{r.points:+d} {r.kind} line {r.line}: {detail}')
    raw = score
    score = max(prefs.minimum, min(prefs.maximum, score))
    if caps: score = min(score, *caps)
    match = 'Excluded' if exclusions else 'Strong' if score >= prefs.strong else 'Good' if score >= prefs.good else 'Consider' if score >= prefs.consider else 'Discarded'
    explanation = f'Config {prefs.fingerprint}; raw {raw}; final {score}. ' + '; '.join(reasons + exclusions or ['No rule matched'])
    return Scored(score, match, explanation, bool(exclusions))
