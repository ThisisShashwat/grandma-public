"""Is this link one a reviewer can use? Pure functions, no Django import: each returns a sentence in Grandma's voice for what is
wrong with a link, or "" when it is fine. A link must be plain ASCII on a real domain name (no address, no home network, no user
name and password in it) over http or https. A playable link may not be on a blocked host; a repository link must be on a
common code host in the form host/owner/repo."""
import re
from ipaddress import ip_address
from urllib.parse import urlsplit

MAX_LENGTH = 300
PORTS = (None, 80, 443)
REPO_HOSTS = ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org", "git.sr.ht")
NOT_PUBLIC_ENDINGS = ("local", "localhost", "internal", "lan", "home", "test", "example", "invalid", "corp", "intranet")

HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}")
NAME = re.compile(r"~?[A-Za-z0-9._-]{1,100}")
BAD_CHARACTER = re.compile(r'[\s\\<>"]')


def web_url_problem(url):
    """What is wrong with a link in general, "" if nothing. Does not look at which host it is."""
    if not url or len(url) > MAX_LENGTH:
        return f"I need a link, dear, and not one longer than {MAX_LENGTH} characters."
    if not url.isascii() or not url.isprintable() or BAD_CHARACTER.search(url):
        return "That link has spaces or odd characters in it. Paste it again, dear."
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return "That doesn't look like a web link."
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return "A web link starts with https://, dear."
    if "@" in parts.netloc:
        return "No user names or passwords in a link, dear. Take them out."
    return host_problem((parts.hostname or "").rstrip(".")) or ("" if port in PORTS else "Leave the port number out, dear.")


def host_problem(host):
    try:
        ip_address(host)
        return "Use the name of the site, dear, not a number."
    except ValueError:
        pass
    if not HOST.fullmatch(host) or host.rsplit(".", 1)[1] in NOT_PUBLIC_ENDINGS:
        return "That isn't a place anyone else can reach, dear."
    return ""


def host_of(url):
    return (urlsplit(url).hostname or "").rstrip(".")


def blocked(host, hosts):
    """Is `host` one of the blocked hosts or a subdomain of one?"""
    return any(host == bad or host.endswith("." + bad) for bad in hosts)


def playable_problem(url, blocked_hosts):
    """A link people can open and try. Not on a host that falls asleep when nobody visits it."""
    url = url.strip()
    problem = web_url_problem(url)
    if problem:
        return problem
    host = host_of(url)
    if blocked(host, blocked_hosts):
        return f"{host} falls asleep when nobody visits it, dear, so I can't use it. Put it somewhere that stays awake."
    return ""


def repo_problem(url):
    """A repository link: https://github.com/owner/repo (also GitLab, Codeberg, Bitbucket, SourceHut), the project's own page."""
    url = url.strip()
    problem = web_url_problem(url)
    if problem:
        return problem
    parts = urlsplit(url)
    host = host_of(url).removeprefix("www.")
    names = [n for n in parts.path.split("/") if n]
    if host not in REPO_HOSTS:
        return "I only read repositories on GitHub, GitLab, Codeberg, Bitbucket or SourceHut, dear."
    if len(names) != 2 or parts.query or parts.fragment or not all(NAME.fullmatch(n) and n.strip(".") for n in names):
        return f"Give me the repository itself, dear, like https://{host}/owner/repo and nothing after it."
    return ""
