"""Shared fixtures for the browser checks.

The review package inlined everything and injected the document with
`set_content`. The published page loads external CSS, JavaScript and an image,
so the checks serve the repository over loopback HTTP and navigate to it. Only
loopback requests are made; outbound links are recorded and cancelled inside
the page, never followed.
"""
from __future__ import annotations

import contextlib
import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'build'

# assets/hero-city.webp as approved in the Horizon v7.2 handoff (MANIFEST.json).
HERO_SHA256 = 'f545120f2f185206424d087e7f2efec032afa214448f79c0a5814a9e532e5d35'

# Outbound clicks are captured and cancelled so no third-party request is made.
CAPTURE_CLICKS = '''() => {
  window.__clicks = [];
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href^="https://"]');
    if (link) { window.__clicks.push(link.href); event.preventDefault(); }
  }, true);
}'''


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class _Server(socketserver.TCPServer):
    allow_reuse_address = True


@contextlib.contextmanager
def serve():
    """Serve the repository root and yield its base URL."""
    handler = functools.partial(_Quiet, directory=str(ROOT))
    with _Server(('127.0.0.1', 0), handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f'http://127.0.0.1:{httpd.server_address[1]}/'
        finally:
            httpd.shutdown()


def launch(playwright, executable: str | None = None):
    options = {'headless': True, 'args': ['--no-sandbox']}
    if executable:
        options['executable_path'] = executable
    return playwright.chromium.launch(**options)


def content() -> dict:
    return json.loads((ROOT / 'data/content.json').read_text(encoding='utf-8'))


def ui(locale: str = 'en') -> dict:
    return json.loads((ROOT / 'data/ui-strings.json').read_text(encoding='utf-8'))[locale]


def write_report(name: str, report: dict) -> None:
    report['passed'] = sum(check['pass'] for check in report['checks'])
    report['failed'] = sum(not check['pass'] for check in report['checks'])
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f'{name}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{name}: {report["passed"]} passed, {report["failed"]} failed')
