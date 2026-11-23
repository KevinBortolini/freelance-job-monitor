"""Local URL handling only; no redirects, URL fetching or link expansion."""
from urllib.parse import urlsplit, urlunsplit, unquote_plus
from .models import MonitorError

HOSTS = {
    '99Freelas': {'99freelas.com.br', 'www.99freelas.com.br'},
    'Freelancer.com': {'freelancer.com', 'www.freelancer.com'},
}
DEMO_HOSTS = {'99Freelas': '99freelas.example', 'Freelancer.com': 'freelancer.example'}

def clean_url(url: str, platform: str, *, demo: bool = False) -> str:
    try:
        if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 for c in url):
            raise ValueError()
        if platform == 'Freelancer.com' and url.startswith('/projects/'):
            url = 'https://' + (DEMO_HOSTS[platform] if demo else 'www.freelancer.com') + url
        p = urlsplit(url)
        allowed = {DEMO_HOSTS[platform]} if demo else HOSTS[platform]
        prefix = '/project/' if platform == '99Freelas' else '/projects/'
        if (p.scheme != 'https' or p.hostname not in allowed or p.username or p.password
                or p.port not in (None, 443) or not p.path.startswith(prefix)
                or not p.path[len(prefix):] or '\\' in url):
            raise ValueError()
        # Preserve unknown raw query values/order/encoding, including IDs and signatures.
        query = '&'.join(part for part in p.query.split('&') if part and not (
            unquote_plus(part.split('=', 1)[0]).casefold().startswith('utm_')
            or unquote_plus(part.split('=', 1)[0]).casefold() in {'fbclid', 'gclid', 'msclkid'}))
        host = p.hostname.removeprefix('www.')
        return urlunsplit(('https', host, p.path, query, ''))
    except (ValueError, KeyError):
        raise MonitorError('Invalid or unsupported project link; no URL was opened.') from None

def job_key(platform: str, link: str, *, demo: bool = False) -> str:
    return platform + '|' + clean_url(link, platform, demo=demo)
