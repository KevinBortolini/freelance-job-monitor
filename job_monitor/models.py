"""Small shared contracts; no account, workbook or network side effects."""
from dataclasses import dataclass

class MonitorError(Exception):
    """An English error safe to show without exposing underlying payloads."""

@dataclass(frozen=True)
class Job:
    platform: str
    title: str
    link: str
    budget: str = ''
    skills: str = ''
    description: str = ''
    category: str = ''
    level: str = ''

    @property
    def search_fields(self):
        return (self.title, self.category, self.skills, self.description)

@dataclass(frozen=True)
class Alert:
    sender: str
    subject: str
    plain: str
    html: str

@dataclass(frozen=True)
class Parsed:
    jobs: tuple[Job, ...]
    issues: tuple[str, ...] = ()

@dataclass(frozen=True)
class Scored:
    score: int
    match: str
    explanation: str
    excluded: bool = False

@dataclass(frozen=True)
class RunResult:
    added: int
    discarded: int
    duplicates: int
