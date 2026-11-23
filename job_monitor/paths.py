"""Keep configuration/runtime operations away from the original project."""
from pathlib import Path
from .models import MonitorError

ROOT = Path(__file__).resolve().parents[1]

def project_path(value: str | Path) -> Path:
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = ROOT / p
    p = p.resolve()
    if not p.is_relative_to(ROOT):
        raise MonitorError('File paths must stay inside this project folder; original project paths are not accepted.')
    return p

def private_path(value: str | Path) -> Path:
    p = project_path(value)
    private = (ROOT / '.local').resolve()
    if private != ROOT / '.local' or not p.is_relative_to(private) or p == private:
        raise MonitorError('Live OAuth, token and output files must be inside this project\'s .local directory.')
    return p
