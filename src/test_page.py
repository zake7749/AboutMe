"""Layout and interaction regression checks for the published page.

python src/test_page.py --theme light
python src/test_page.py --theme dark

Requires Playwright, BeautifulSoup4 and a Chromium build (Playwright's own by
default; --chromium overrides). The page is served over loopback HTTP so its
external stylesheet, script and image load the way a reader gets them. No
third-party page is visited: outbound clicks are recorded and cancelled.

Ported from the Horizon v7.2 review suite. Checks tied to the review package
(inlined assets, the light/dark companion file, the frozen content snapshot)
are replaced by their production equivalents; everything else is unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from qa_support import CAPTURE_CLICKS, HERO_SHA256, ROOT, content, launch, serve, ui, write_report

PAGE = 'about/index.html'
EXTERNAL_ASSETS = {'css/horizon.css', 'js/horizon.js', 'assets/hero-city.webp', 'favicon.png'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--theme', choices=['light', 'dark'], required=True)
    ap.add_argument('--chromium', default=None)
    args = ap.parse_args()
    theme = args.theme
    html = (ROOT / PAGE).read_text(encoding='utf-8')
    data = content()
    strings = ui('en')
    report = {'entry': PAGE, 'engine': 'Chromium', 'starting_theme': theme,
              'load_method': 'loopback HTTP; no third-party requests', 'checks': [],
              'limitations': ['No Safari/Firefox or physical iPhone test',
                              'External page availability not checked',
                              'No deployment performed']}

    def check(name, ok, info=None):
        report['checks'].append({'name': name, 'pass': bool(ok), 'detail': info})
        if not ok:
            raise AssertionError(f'{name}: {info}')

    try:
        doc = BeautifulSoup(html, 'html.parser')
        check('Language and no-script default theme', doc.html.get('lang') == 'en' and doc.html.get('data-theme') == 'light')
        check('Review-only robots directive removed', not doc.select('meta[name="robots"]'))
        check('Canonical URL and description present',
              doc.select_one('link[rel="canonical"]') is not None and doc.select_one('meta[name="description"]') is not None)
        # Easy to change apart, and the page would then point readers and
        # crawlers at somewhere it is not served from.
        origin = data['origin'].rstrip('/')
        absolute = [doc.select_one('link[rel="canonical"]')['href'],
                    doc.select_one('meta[property="og:url"]')['content'],
                    doc.select_one('meta[property="og:image"]')['content']]
        check('Absolute URLs match the declared origin',
              all(u.startswith(origin + '/') for u in absolute), {'origin': origin, 'urls': absolute})
        # The root hands readers on rather than serving a second copy of the page.
        root = BeautifulSoup((ROOT / 'index.html').read_text(encoding='utf-8'), 'html.parser')
        target = posixpath.dirname(PAGE) + '/'
        check('Root redirects to the page and names it canonical',
              root.select_one('meta[http-equiv="refresh"]')['content'].endswith('url=' + target)
              and root.select_one('link[rel="canonical"]')['href'] == f'{origin}/{target}'
              and not root.select('.publication-item'))
        ids = [tag['id'] for tag in doc.select('[id]')]
        check('Unique document and SVG identifiers', len(ids) == len(set(ids)))
        check('Seven publication entries', len(doc.select('.publication-item')) == 7)
        check('Four competition entries', len(doc.select('.competition')) == 4)
        check('No nested interactive controls', len(doc.select('a a, a button, button a, button button')) == 0)
        here = posixpath.dirname(PAGE)
        referenced = {posixpath.normpath(posixpath.join(here, tag.get('href') or tag.get('src')))
                      for tag in doc.select('link[rel="stylesheet"], link[rel="icon"], script[src], img[src]')}
        check('Only the expected local assets are referenced', referenced == EXTERNAL_ASSETS, sorted(referenced))
        check('Every referenced asset exists', all((ROOT / path).is_file() for path in referenced))
        # An asset the page stopped using would otherwise ship unnoticed.
        stray = sorted(f'assets/{f.name}' for f in (ROOT / 'assets').iterdir()
                       if f.is_file() and f'assets/{f.name}' not in referenced)
        check('No unreferenced asset ships with the page', not stray, stray)
        check('Approved hero image unchanged', hashlib.sha256((ROOT / 'assets/hero-city.webp').read_bytes()).hexdigest() == HERO_SHA256)
        check('Seven original Abstracts with two paragraphs each',
              len(doc.select('.publication-abstract')) == 7 and
              all(len(e.select('p')) == 2 and e.h4.get_text() == strings['abstract'] for e in doc.select('.publication-abstract')))
        check('Rendered Abstracts match reviewed source data', all(
            [e.get_text() for e in doc.select(f'#publication-{p["id"]} .publication-abstract p')] == p['abstract_en']
            for p in data['publications']))
        check('Abstract lengths are between 130 and 180 words', all(
            130 <= len(' '.join(p['abstract_en']).split()) <= 180 for p in data['publications']))
        credential = doc.select('.other-honors a')
        check('One Kaggle Competition Master profile link replaces Top 1% rows',
              len(credential) == 1 and credential[0].get_text() == 'Kaggle Competition Master' and
              credential[0]['href'] == 'https://www.kaggle.com/zake7749' and 'Top 1%' not in doc.get_text())
        hero_links = [a['href'] for a in doc.select('.hero-socials a')]
        footer_links = [a['href'] for a in doc.select('.footer-socials a')]
        check('Identical Hero and footer destinations/order', len(hero_links) == 4 and hero_links == footer_links)
        check('Accessible icon labels and local SVGs', all(a.get('aria-label') and a.get('title') and a.svg for a in doc.select('.social-link')))
        toggle = doc.select_one('.theme-toggle')
        check('Theme switch is a native button, not a link to a companion file',
              toggle is not None and toggle.name == 'button' and toggle.get('type') == 'button' and toggle.get('href') is None)
        check('Theme switch carries both accessible labels',
              bool(toggle.get('data-label-dark')) and bool(toggle.get('data-label-light')))
        chrome = doc.select_one('meta[name="theme-color"]')
        check('Browser chrome colour is declared for both palettes',
              chrome is not None and bool(chrome.get('data-light')) and bool(chrome.get('data-dark'))
              and chrome['data-light'] != chrome['data-dark'])
        # A title links to the entry's primary repository and the list below
        # names every repository, so the two overlap by design. What must not
        # repeat is a destination inside one list.
        listed = [[a['href'] for a in item.select('.resource-actions a')]
                  for item in doc.select('.resource-item')]
        check('No repository is listed twice in one entry',
              all(len(hrefs) == len(set(hrefs)) for hrefs in listed), listed)
        groups = doc.select('.publication-group')
        check('Publications are split into papers and technical writing',
              [g.get_text() for g in groups] == ['Papers', 'Technical writing'] and
              len(doc.select('.publication-list')) == 2)
        check('One byline across every record',
              'Justin Yang' not in doc.select_one('#publication .publication-list').get_text())
        check('The blog is reachable from the writing it belongs with',
              doc.select_one('.writing-note a[href="https://zake7749.github.io/"]') is not None)
        check('Original source URLs and author order preserved', all(
            doc.select_one(f'#publication-{p["id"]} .publication-title')['href'] == p['primary_url'] and
            doc.select_one(f'#publication-{p["id"]} .authors').get_text() == ', '.join(p['authors'])
            for p in data['publications'] if p.get('publish', True)))

        with serve() as base_url, sync_playwright() as pw:
            b = launch(pw, args.chromium)
            context = b.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
            # Seeds the starting theme before the document's own head script runs.
            # Only when unset, so a reload still sees what the toggle stored.
            context.add_init_script(f"try{{if(!localStorage.getItem('theme'))localStorage.setItem('theme','{theme}')}}catch(e){{}}")
            page = context.new_page()
            page.set_default_timeout(4500)
            errors, failed = [], []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('requestfailed', lambda r: failed.append(r.url))
            page.on('response', lambda r: failed.append(f'{r.status} {r.url}') if r.status >= 400 else None)
            page.goto(base_url + 'about/', wait_until='load')
            page.wait_for_timeout(120)
            check('All page assets load', not failed, failed)
            check('Stored theme applied at first paint', page.locator('html').get_attribute('data-theme') == theme)
            check('Native HTML enhanced without script errors', not errors, errors)
            check('Publication details collapsed by enhancement', page.locator('.publication-detail[hidden]').count() == 7)
            check('Competition details collapsed by enhancement', page.locator('.competition-detail[hidden]').count() == 4)
            for width in [320, 360, 390, 430, 600, 760, 768, 900, 1100, 1440, 1920]:
                page.set_viewport_size({'width': width, 'height': 844 if width < 760 else 900})
                page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                page.wait_for_timeout(40)
                state = page.evaluate('''() => ({overflow:document.documentElement.scrollWidth>innerWidth,
                    headerHeight:document.querySelector('.site-nav').getBoundingClientRect().height,
                    themeWidth:document.querySelector('.theme-toggle').getBoundingClientRect().width,
                    brandRight:document.querySelector('.brand').getBoundingClientRect().right,
                    toolsLeft:document.querySelector('.nav-tools').getBoundingClientRect().left})''')
                check(f'Width {width}: no horizontal overflow or navbar overlap',
                      not state['overflow'] and state['brandRight'] < state['toolsLeft'] and state['themeWidth'] >= 44, state)
                # The last row is either full or taken by a single wide card.
                grid = page.evaluate('''() => {
                    const g = document.querySelector('.project-grid');
                    const columns = getComputedStyle(g).gridTemplateColumns.split(' ').length;
                    const cards = g.children.length;
                    const last = g.lastElementChild.getBoundingClientRect();
                    return {columns, cards, spansRow: Math.abs(last.width - g.getBoundingClientRect().width) < 2};
                }''')
                check(f'Width {width}: projects leave no empty grid cell',
                      grid['cards'] % grid['columns'] == 0 or grid['spansRow'], grid)
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
            page.wait_for_timeout(60)
            lists = page.locator('.resource-list').evaluate_all(
                '(es)=>es.map(e=>[getComputedStyle(e).gridTemplateRows.split(" ").length, e.children.length])')
            check('Platform panels reserve no empty resource row', all(rows == items for rows, items in lists), lists)
            edges = page.evaluate('''() => {
                const left = el => Math.round(el.getBoundingClientRect().left);
                return {about: left(document.querySelector('.about-copy')),
                        heading: left(document.querySelector('.about-grid h2')),
                        projects: left(document.querySelector('#work .section-heading h2'))};
            }''')
            check('About reads on the same left edge as the rest of the page',
                  edges['about'] == edges['heading'] == edges['projects'], edges)
            copy_fill = page.evaluate('''() => {
                const copy = document.querySelector('.about-copy').getBoundingClientRect();
                const shell = document.querySelector('.about.shell').getBoundingClientRect();
                const tracks = getComputedStyle(document.querySelector('.about-copy')).gridTemplateColumns.split(' ').length;
                const last = [...document.querySelectorAll('.about-copy p')].pop().getBoundingClientRect();
                return {tracks, slackRight: Math.round(copy.right - last.right)};
            }''')
            check('About copy uses the width it is given', copy_fill['tracks'] == 3 and copy_fill['slackRight'] < 8, copy_fill)
            # `.about-copy p` outranks a bare `.about-lead`, so this is easy to lose.
            lead = page.evaluate('''() => {
                const el = document.querySelector('.about-lead');
                const body = el.nextElementSibling;
                const a = getComputedStyle(el), b = getComputedStyle(body);
                return {lead: [a.fontSize, a.fontWeight, a.color], body: [b.fontSize, b.fontWeight, b.color]};
            }''')
            check('About lead is set apart from the body copy',
                  lead['lead'][0] != lead['body'][0] and lead['lead'][1] != lead['body'][1]
                  and lead['lead'][2] != lead['body'][2], lead)
            check('Transparent first-screen nav surface', page.locator('.nav-surface').evaluate('(e)=>getComputedStyle(e).backgroundColor') == 'rgba(0, 0, 0, 0)')
            check('Enhanced header is fixed', page.locator('.site-nav').evaluate('(e)=>getComputedStyle(e).position') == 'fixed')
            page.evaluate(CAPTURE_CLICKS)
            for i in range(7):
                button = page.locator('.publication-toggle').nth(i)
                button.click()
                check(f'Publication {i+1}: click opens summary', button.get_attribute('aria-expanded') == 'true')
                title = page.locator('.publication-title').nth(i)
                url = title.get_attribute('href')
                title.click()
                check(f'Publication {i+1}: title is original URL, not a toggle',
                      page.evaluate('__clicks.at(-1)') == url and button.get_attribute('aria-expanded') == 'true')
                button.click()
            venue = page.locator('.publication-venue').first
            venue.scroll_into_view_if_needed()
            box = venue.bounding_box()
            page.mouse.click(box['x'] + 2, box['y'] + 3)
            check('Publication metadata area opens panel', page.locator('.publication-toggle').first.get_attribute('aria-expanded') == 'true')
            page.locator('.publication-toggle').first.focus()
            page.keyboard.press('Space')
            check('Space closes publication panel', page.locator('.publication-toggle').first.get_attribute('aria-expanded') == 'false')
            page.keyboard.press('Enter')
            check('Enter reopens publication panel', page.locator('.publication-toggle').first.get_attribute('aria-expanded') == 'true')
            for i in range(4):
                button = page.locator('.competition-toggle').nth(i)
                button.click()
                url = page.locator('.competition-title').nth(i).get_attribute('href')
                page.locator('.competition-title').nth(i).click()
                check(f'Competition {i+1}: original title link separate from disclosure',
                      button.get_attribute('aria-expanded') == 'true' and page.evaluate('__clicks.at(-1)') == url)
                button.click()
            page.locator('.publication-toggle').nth(1).click()
            page.locator('#publication').scroll_into_view_if_needed()
            page.wait_for_timeout(70)
            page.locator('.publication-toggle').first.hover()
            backgrounds = page.locator('.publication-header').evaluate_all('(es)=>es.map(e=>getComputedStyle(e).backgroundColor)')
            check('Publication has no hover/expanded highlight block', all(c == 'rgba(0, 0, 0, 0)' for c in backgrounds), backgrounds)

            before = page.evaluate('scrollY')
            open_before = page.locator('.publication-toggle[aria-expanded="true"]').count()
            page.locator('.theme-toggle').click()
            page.wait_for_timeout(40)
            other = 'dark' if theme == 'light' else 'light'
            check('Theme changes in place', page.locator('html').get_attribute('data-theme') == other)
            check('Theme switch preserves scroll and expanded panels',
                  abs(page.evaluate('scrollY') - before) < 2 and page.locator('.publication-toggle[aria-expanded="true"]').count() == open_before)
            check('Switch relabels itself to offer the opposite theme',
                  page.locator('.theme-toggle').get_attribute('aria-label') == strings[f'switch_to_{theme}'])
            check('Choice is stored', page.evaluate("localStorage.getItem('theme')") == other)
            check('Browser chrome colour follows the switch',
                  page.evaluate("document.querySelector('meta[name=\"theme-color\"]').content")
                  == page.evaluate(f"document.querySelector('meta[name=\"theme-color\"]').dataset['{other}']"))
            page.reload(wait_until='load')
            page.wait_for_timeout(80)
            check('Stored choice survives a reload', page.locator('html').get_attribute('data-theme') == other)
            page.evaluate(CAPTURE_CLICKS)
            page.locator('.theme-toggle').focus()
            page.keyboard.press('Space')
            check('Keyboard Space switches theme', page.locator('html').get_attribute('data-theme') == theme)

            page.evaluate("scrollTo({top:document.querySelector('.hero').offsetHeight+70,behavior:'instant'})")
            page.wait_for_timeout(100)
            check('Navbar contrast follows reading surface', not page.locator('.site-nav').evaluate('(e)=>e.classList.contains("over-hero")'))
            check('No extra filter mask below header', page.locator('.nav-surface').evaluate('(e)=>getComputedStyle(e).maskImage') == 'none')
            for a in page.locator('.footer-socials a').all():
                href = a.get_attribute('href')
                a.click()
                check('Footer icon routes to ' + a.get_attribute('data-social'), page.evaluate('__clicks.at(-1)') == href)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.evaluate('scrollTo(0,0)')
            page.wait_for_timeout(60)
            page.locator('.mobile-menu summary').click()
            check('Mobile menu opens', page.locator('.mobile-menu').get_attribute('open') is not None)
            page.keyboard.press('Escape')
            check('Escape closes mobile menu', page.locator('.mobile-menu').get_attribute('open') is None)
            page.locator('.mobile-menu summary').click()
            page.locator('.mobile-nav a[href="#publication"]').click()
            check('Mobile anchor closes menu', page.locator('.mobile-menu').get_attribute('open') is None)
            page.wait_for_timeout(60)
            for button in page.locator('.publication-toggle').all():
                if button.get_attribute('aria-expanded') == 'false':
                    button.click()
            check('All expanded on mobile: no overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            for width in [320, 360, 390, 430, 760, 1440]:
                page.set_viewport_size({'width': width, 'height': 844 if width < 760 else 900})
                page.wait_for_timeout(30)
                check(f'Expanded abstracts at {width}px: readable without clipping',
                      page.evaluate('document.documentElement.scrollWidth <= innerWidth') and
                      page.locator('.publication-abstract:visible').count() == 7)
            # Named rather than positional: the record's group and order may change.
            page.set_viewport_size({'width': 390, 'height': 844})
            target = page.locator('#publication-kyara-article-2025 .publication-toggle')
            if target.get_attribute('aria-expanded') == 'true':
                target.click()
            page.evaluate("location.hash='publication-detail-kyara-article-2025'")
            page.wait_for_timeout(90)
            check('Direct detail hash reveals panel', target.get_attribute('aria-expanded') == 'true')
            for button in page.locator('.publication-toggle').all():
                if button.get_attribute('aria-expanded') == 'true':
                    button.click()
            page.emulate_media(media='print')
            check('Print reveals all publication details',
                  all(x != 'none' for x in page.locator('.publication-detail').evaluate_all('(es)=>es.map(e=>getComputedStyle(e).display)')))
            check('No runtime errors', not errors, errors)
            context.close()

            # Reader with scripting blocked: the page is still a complete document.
            nojs = b.new_context(java_script_enabled=False, viewport={'width': 390, 'height': 844})
            page = nojs.new_page()
            page.goto(base_url + 'about/', wait_until='load')
            check('No-script publications remain readable', page.locator('.publication-detail:visible').count() == 7)
            check('No-script Abstract paragraphs are all visible', page.locator('.publication-abstract p:visible').count() == 14)
            check('No-script competitions remain readable', page.locator('.competition-detail:visible').count() == 4)
            check('No-script disclosure buttons hidden',
                  page.locator('.publication-toggle:visible').count() == 0 and page.locator('.competition-toggle:visible').count() == 0)
            check('No-script theme switch hides itself', page.locator('.theme-toggle:visible').count() == 0)
            check('No-script header stays on Hero', page.locator('.site-nav').evaluate('(e)=>getComputedStyle(e).position') == 'absolute')
            check('No-script header has no white plate', page.locator('.nav-surface').evaluate('(e)=>getComputedStyle(e).backgroundColor') == 'rgba(0, 0, 0, 0)')
            page.locator('.mobile-menu summary').click()
            check('No-script native menu opens', page.locator('.mobile-nav').is_visible())
            nojs.close()
            b.close()
    except Exception as exc:
        report['exception'] = str(exc)
        raise
    finally:
        write_report(f'qa-{theme}', report)


if __name__ == '__main__':
    main()
