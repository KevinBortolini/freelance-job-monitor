"""Tests use new destination-local temporary files and never real credentials."""
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
(ROOT/'.test-data').mkdir(exist_ok=True)

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def blocked(*args,**kwargs):raise AssertionError('Network access is forbidden in tests.')
    monkeypatch.setattr(socket.socket,'connect',blocked)
    monkeypatch.setattr(socket,'create_connection',blocked)

@pytest.fixture
def prefs():
    from job_monitor.preferences import load_preferences
    return load_preferences(ROOT/'preferences.example.txt')

@pytest.fixture
def jobs():
    from job_monitor.parsers import read_eml,parse_alert
    result=[]
    for p in sorted((ROOT/'tests/fixtures').glob('*.eml')):result.extend(parse_alert(read_eml(p.read_bytes()),demo=True).jobs)
    return result
