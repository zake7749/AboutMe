"""Build the public About page from data/content.json.

Migrated from the Horizon v7.2 review package. What changed for production:

* CSS, JavaScript and the hero image are emitted as external files instead of
  being inlined, so the page is cacheable and the assets stay reviewable.
* One page per locale with an in-place theme switch. The review package shipped
  two entry files that linked to each other; here a single page remembers the
  reader's choice and falls back to the system preference.
* The review-only `noindex,nofollow` is gone, and the page carries a real
  title, description and canonical URL.
* Every string the page renders now resolves through `tx()` (authored content,
  from content.json) or `S()` (interface chrome, from ui-strings.json), so a
  second locale is a data change rather than a template change.

Usage:
    python src/build.py              # build every locale in BUILD_LOCALES
    python src/build.py --check zh   # report what zh still needs, build nothing

Requires Python 3.10+; standard library only.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
DATA = json.loads((ROOT / 'data/content.json').read_text(encoding='utf-8'))
UI = json.loads((ROOT / 'data/ui-strings.json').read_text(encoding='utf-8'))
E = html.escape
PLUS = '<svg class="plus" viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M4 10h12"/><path class="plus-vertical" d="M10 4v12"/></svg>'

# Where the page is served from. The canonical link, og:url and og:image are
# built from these, so they travel with the data rather than the template.
CANONICAL_ORIGIN = DATA['origin'].rstrip('/')
BASE_PATH = DATA.get('base_path', '/')

# Output targets. `prefix` is how the page reaches repository-root assets.
# The root is reserved: if the blog ever moves to this domain it has to take
# the root, so every post keeps the path it has today. `out` is where the page
# sits under the deployment root, `prefix` how it reaches root-level assets.
LOCALES = {
    'en': {'lang': 'en', 'out': 'about/index.html', 'prefix': '../'},
    'zh': {'lang': 'zh-Hant', 'out': 'zh/about/index.html', 'prefix': '../../'},
}
# zh joins this list once its copy lands in content.json and ui-strings.json.
# `python src/build.py --check zh` lists exactly what is still missing.
BUILD_LOCALES = ['en']

CSS_OUT = 'css/horizon.css'
JS_OUT = 'js/horizon.js'
HERO_ASSET = 'assets/hero-city.webp'
FAVICON = 'favicon.png'

LOCALE = 'en'
MISSING: list[str] = []


# --- text resolution ---------------------------------------------------------

def tx(obj: dict, key: str, where: str = ''):
    """Authored content, resolved for the active locale.

    Looks for `key_<locale>`, then `key_en`, then a bare `key`. Anything that
    falls back while building a non-English page is recorded in MISSING.
    """
    for candidate in (f'{key}_{LOCALE}', f'{key}_en', key):
        value = obj.get(candidate)
        if value not in (None, '', [], {}):
            if LOCALE != 'en' and candidate != f'{key}_{LOCALE}':
                MISSING.append(f'content: {where or obj.get("id", "?")}.{key}_{LOCALE}')
            return value
    raise KeyError(f'{where or obj.get("id", "?")}: no value for {key!r}')


def S(key: str, **fmt) -> str:
    """Interface chrome, resolved for the active locale."""
    value = (UI.get(LOCALE) or {}).get(key)
    if not value:
        if LOCALE != 'en':
            MISSING.append(f'ui-strings: {LOCALE}.{key}')
        value = UI['en'][key]
    return value.format(**fmt) if fmt else value


def months() -> list[str]:
    value = (UI.get(LOCALE) or {}).get('months')
    if not value or len(value) != 12:
        if LOCALE != 'en':
            MISSING.append(f'ui-strings: {LOCALE}.months')
        value = UI['en']['months']
    return value


def foreign(text: str, lang: str) -> str:
    """Mark a run of text whose language differs from the page language."""
    page_lang = LOCALES[LOCALE]['lang']
    if lang == page_lang or page_lang.startswith(lang):
        return E(text)
    return f'<span lang="{lang}">{E(text)}</span>'


# --- building blocks ---------------------------------------------------------

def anchor(url: str, text: str, cls: str = '', context: str = '') -> str:
    if not isinstance(url, str) or not url.startswith(('https://', 'mailto:', '#')):
        raise ValueError(f'Unexpected URL: {url!r}')
    external = url.startswith('https://')
    extra = ' target="_blank" rel="noopener noreferrer"' if external else ''
    accessible_name = text + (' — ' + context if context else '') + (' ' + S('opens_in_new_tab') if external else '')
    aria = f' aria-label="{E(accessible_name, quote=True)}"' if (context or external) else ''
    return (f'<a class="{E(cls, quote=True)}" href="{E(url, quote=True)}"{extra}{aria}>'
            f'<span>{E(text)}</span></a>')


def links(items: list[dict], context: str = '', cls: str = '') -> str:
    if not items:
        return ''
    return f'<div class="links {E(cls)}">' + ''.join(
        anchor(x['url'], tx(x, 'label', 'link'), context=context) for x in items) + '</div>'


def provenance(item: dict) -> str:
    return ' data-sources="' + E(' '.join(item.get('source_ids', [])), quote=True) + '"'


def heading(title: str, action: str = '') -> str:
    return f'<div class="section-heading"><h2>{E(title)}</h2>{action}</div>'


def theme_toggle() -> str:
    """In-place switch. The review package used a link to a companion file;
    production has one page per locale, so this is a button that persists the
    choice. Without scripting it cannot do anything, so it hides itself."""
    return f'''<button class="theme-toggle" type="button" data-theme-toggle
      aria-label="{E(S('switch_to_dark'), quote=True)}" title="{E(S('switch_to_dark'), quote=True)}"
      data-label-dark="{E(S('switch_to_dark'), quote=True)}" data-label-light="{E(S('switch_to_light'), quote=True)}">
      <svg class="theme-moon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="M20.2 14.1A8.5 8.5 0 0 1 9.9 3.8 8.5 8.5 0 1 0 20.2 14.1Z"/></svg>
      <svg class="theme-sun" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="3.6"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42m0-14.14-1.42 1.42M6.35 17.65l-1.42 1.42"/></svg>
    </button>'''


def navigation() -> str:
    name = DATA['profile']['display_name']
    items = ''.join(anchor(n['href'], tx(n, 'label', 'navigation')) for n in DATA['navigation'])
    return f'''<header class="site-nav over-hero" id="site-header"><div class="nav-surface" aria-hidden="true"></div><div class="shell nav-inner">
      <a class="brand" href="#top" aria-label="{E(S('back_to_top_aria', name=name), quote=True)}">{E(name)}<span class="brand-period" aria-hidden="true">.</span></a>
      <nav class="desktop-nav" aria-label="{E(S('main_navigation'), quote=True)}">{items}</nav>
      <div class="nav-tools">{theme_toggle()}
        <details class="mobile-menu"><summary aria-label="{E(S('toggle_navigation'), quote=True)}"><span>{E(S('menu'))}</span><svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M3 6h14M3 14h14"/></svg></summary>
          <nav class="mobile-nav" aria-label="{E(S('mobile_navigation'), quote=True)}">{items}</nav>
        </details>
      </div>
    </div></header>'''


def social_links(location: str = 'hero') -> str:
    icons = []
    for link in DATA['hero']['social_links']:
        icon_path = ROOT / 'assets' / 'icons' / (link['icon'] + '.svg')
        svg = icon_path.read_text(encoding='utf-8')
        svg = svg.replace('<svg ', '<svg aria-hidden="true" focusable="false" ', 1)
        # The HF mask has a local SVG id. Repeated icons must have unique ids.
        svg = svg.replace('hf-social-mask', f'hf-social-mask-{location}')
        label = E(tx(link, 'label', 'social_links'), quote=True)
        icons.append(f'''<a class="social-link" href="{E(link['url'], quote=True)}"
          data-social="{E(link['id'])}" target="_blank" rel="noopener noreferrer"
          aria-label="{label} {E(S('opens_in_new_tab'), quote=True)}" title="{label}">{svg}</a>''')
    return f'<nav class="social-links {location}-socials" aria-label="{E(S("profiles_and_blog"), quote=True)}">' + ''.join(icons) + '</nav>'


def hero(prefix: str) -> str:
    h = DATA['hero']
    return f'''<section aria-labelledby="hero-title" class="hero">
      <img class="hero-photo" alt="" width="1672" height="941" src="{prefix}{HERO_ASSET}" fetchpriority="high" decoding="async">
      <div class="shell hero-body"><p class="hero-eyebrow">{E(tx(h, 'eyebrow', 'hero'))}</p>
        <h1 id="hero-title">{E(tx(h, 'headline', 'hero'))}</h1>
        <p class="hero-tagline">{E(tx(h, 'tagline', 'hero'))}</p>
        <p class="hero-intro">{E(tx(h, 'introduction', 'hero'))}</p>
        {social_links()}
      </div></section>'''


def about(prefix: str) -> str:
    """The heading carries no name block: the hero, the nav brand and the footer
    already say who this is."""
    a = DATA['introduction']
    lead = f'<p class="about-lead">{E(tx(a, "lead", "introduction"))}</p>'
    ps = lead + ''.join(f'<p>{E(text)}</p>' for text in tx(a, 'paragraphs', 'introduction'))
    portrait = DATA['profile'].get('portrait_asset')
    photo = ''
    if portrait:
        photo = (f'<img class="about-portrait" src="{prefix}{E(portrait["src"], quote=True)}" '
                 f'width="{portrait["width"]}" height="{portrait["height"]}" loading="lazy" decoding="async" '
                 f'alt="{E(DATA["profile"]["display_name"], quote=True)}">')
    grid = 'about-grid has-portrait' if photo else 'about-grid'
    return f'''<section class="section about shell" id="about"{provenance(a)}>
      <div class="{grid}"><h2>{E(tx(a, 'heading', 'introduction'))}</h2>{photo}
      <div class="about-copy">{ps}</div></div></section>'''


def project_outcome(project: dict) -> str:
    """A separate citation-like result line, outside the primary card hit area.

    Competition identities point to official events, never to a project repo.
    Prize amounts identify the entry's award, not the owner's personal earnings.
    """
    competition_ref = project.get('competition_ref')
    if not competition_ref:
        return E(tx(project, 'detail', 'project'))
    award = next((a for a in DATA['awards'] if a['id'] == competition_ref), None)
    if award is None:
        raise ValueError(f'Unknown competition reference: {competition_ref}')
    chunks = [
        f'<span class="outcome-placement">{E(S("place", rank=tx(award, "rank", "award")))}</span>',
        anchor(award['official_url'], tx(project, 'competition_link_label', 'project'),
               'project-competition-link', S('official_competition', name=award['name'])),
        f'<span class="outcome-year">{E(award["year"])}</span>',
    ]
    prize = project.get('prize')
    if prize:
        amount = prize.get('amount')
        if (prize.get('currency') != 'USD' or isinstance(amount, bool)
                or not isinstance(amount, int) or amount <= 0):
            raise ValueError('Expected a positive whole-dollar USD prize')
        aria = S('prize_aria', amount=f'{amount:,}')
        chunks.append(f'<span class="project-prize" aria-label="{E(aria, quote=True)}">US${amount:,} {E(tx(prize, "display_label", "prize"))}</span>')
    return '<span class="outcome-separator" aria-hidden="true"> · </span>'.join(chunks)


def projects() -> str:
    cards = []
    for p in DATA['projects']:
        if not p.get('publish', True):
            continue
        title = anchor(p['primary_url'], p['title'], 'primary-link', tx(p, 'primary_label', 'project'))
        cards.append(f'''<article class="project-card interactive-card" id="project-{E(p['id'])}"{provenance(p)}>
          <p class="project-category">{E(tx(p, 'category', 'project'))}</p>
          <h3>{title}</h3><p class="project-subtitle">{E(tx(p, 'subtitle', 'project'))}</p>
          <p class="project-description">{E(tx(p, 'description', 'project'))}</p>
          <div class="project-bottom"><p class="project-outcome">{project_outcome(p)}</p>{links(p['secondary_links'], p['title'], 'secondary-links')}</div>
        </article>''')
    return f'''<section class="section projects shell" id="work">
      {heading(S('projects_heading'))}<div class="project-grid" data-count="{len(cards)}">{''.join(cards)}</div>
      {open_source()}</section>'''


def open_source() -> str:
    """The platform owns its metrics. Explicit related links avoid duplicate code CTAs."""
    source = DATA['open_source']
    panels = []
    for group in source['groups']:
        rows = []
        for item in group['items']:
            # An entry that gathers several repositories has no single home, so
            # its heading is plain text and the repositories are the links.
            title = (anchor(item['primary_url'], tx(item, 'title', 'open_source item'), 'resource-title',
                            tx(item, 'primary_label', 'open_source item'))
                     if item.get('primary_url') else E(tx(item, 'title', 'open_source item')))
            additional = links(item.get('secondary_links', []), item['title'], 'resource-actions')
            rows.append(f'''<article class="resource-item" data-resource-id="{E(item['id'])}"{provenance(item)}>
              <h5>{title}</h5><p>{E(tx(item, 'description', 'open_source item'))}</p>{additional}</article>''')
        top = anchor(group['url'], group['platform'], 'platform-link', tx(group, 'heading', 'open_source group'))
        stats = ''.join(f'''<div class="platform-stat" data-metric="{E(m['id'])}" title="{E(tx(m, 'tooltip', 'metric'), quote=True)}"{provenance(m)}>
          <span class="stat-value">{E(m['display'])}</span><span class="stat-label">{E(tx(m, 'label', 'metric'))}</span></div>''' for m in group['metrics'])
        panels.append(f'''<section class="platform-panel" data-platform="{E(group['id'])}" aria-labelledby="platform-{E(group['id'])}">
          <div class="platform-heading"><div class="platform-identity"><h4 id="platform-{E(group['id'])}">{top}</h4><p>{E(tx(group, 'heading', 'open_source group'))}</p></div>
            <div class="platform-stats" aria-label="{E(S('platform_profile_aria', platform=group['platform']), quote=True)}">{stats}</div></div>
          <div class="resource-list">{''.join(rows)}</div></section>''')
    return f'''<section class="open-source" id="open-source" aria-labelledby="open-source-title"{provenance(source)}>
      <div class="open-source-heading"><div><h3 id="open-source-title">{E(tx(source, 'title', 'open_source'))}</h3><p>{E(tx(source, 'summary', 'open_source'))}</p></div></div>
      <div class="platform-grid">{''.join(panels)}</div></section>'''


def competitions() -> str:
    rows = []
    for a in DATA['awards']:
        aid = E(a['id'])
        title = anchor(a['official_url'], a['name'], 'competition-title', S('official_competition', name=a['name']))
        rows.append(f'''<article class="competition" id="competition-{aid}"{provenance(a)}>
          <div class="competition-summary">
            <span class="competition-year">{E(a['year'])}</span>
            <div class="competition-copy"><h3 id="competition-title-{aid}">{title}</h3>
              <p>{E(a['organizer'])}<span class="separator" aria-hidden="true"> · </span>{E(tx(a, 'description', 'award'))}</p></div>
            <span class="result-label">{E(S('place', rank=tx(a, 'rank', 'award')))}</span>
            <button class="competition-toggle" type="button" aria-expanded="true" aria-controls="competition-detail-{aid}" aria-label="{E(S('competition_toggle_aria', name=a['name']), quote=True)}">{PLUS}</button>
          </div>
          <div class="competition-detail" id="competition-detail-{aid}" role="region" aria-labelledby="competition-title-{aid}">
            <div class="detail-task"><h4>{E(S('the_task'))}</h4><p>{E(tx(a, 'task', 'award'))}</p></div>
            <div class="detail-solution"><h4>{E(S('the_solution'))} <span>· {E(a['solution_label'])}</span></h4><p>{E(tx(a, 'solution', 'award'))}</p>{links(a['links'], a['name'])}</div>
          </div></article>''')
    extras = ''.join(anchor(h['url'], tx(h, 'label', 'recognition'))
                     for h in DATA['additional_recognition'] if h.get('url'))
    return f'''<section class="section recognition-section" id="competitions"><div class="shell">
      {heading(S('competitions_heading'))}<div class="competition-list">{''.join(rows)}</div>
      <div class="other-honors" aria-label="{E(S('recognition_aria'), quote=True)}">{extras}</div>
    </div></section>'''


def publication_row(p: dict, names: tuple[str, ...]) -> str:
    """One record. The title is a direct reading link; the rest of the header
    area is a disclosure. Every detail is present in static HTML and visible
    when scripts are blocked. Author order and source URLs are retained;
    abstracts are source-reviewed editorial paraphrases."""
    pid = p['id']
    authors = ', '.join(f'<strong>{E(a)}</strong>' if a in names else E(a) for a in p['authors'])
    title = anchor(p['primary_url'], p['title'], 'publication-title', tx(p, 'primary_label', 'publication'))
    actions = [{'url': p['primary_url'], 'label': tx(p, 'primary_label', 'publication')}] + p['secondary_links']
    paragraphs = tx(p, 'abstract', f'publication {pid}')
    if not isinstance(paragraphs, list) or len(paragraphs) != 2 or not all(isinstance(x, str) and x.strip() for x in paragraphs):
        raise ValueError(f'Publication {pid}: expected two non-empty abstract paragraphs')
    abstract = ''.join(f'<p>{E(text)}</p>' for text in paragraphs)
    return f'''<article class="publication-item" id="publication-{E(pid)}"{provenance(p)} data-publication-type="{E(p['type'])}">
          <div class="publication-header">
            <span class="publication-year">{p['year']}</span>
            <div class="publication-body">
              <p class="publication-venue">{E(p['display_venue'])}<span class="publication-type">{E(tx(p, 'primary_label', 'publication'))}</span></p>
              <h3 id="publication-title-{E(pid)}">{title}</h3>
            </div>
            <button class="publication-toggle" type="button" aria-expanded="true" aria-controls="publication-detail-{E(pid)}" aria-label="{E(S('publication_toggle_aria', title=p['title']), quote=True)}">{PLUS}</button>
          </div>
          <div class="publication-detail" id="publication-detail-{E(pid)}" role="region" aria-labelledby="publication-title-{E(pid)}">
            <div class="publication-abstract" aria-labelledby="abstract-label-{E(pid)}">
              <h4 id="abstract-label-{E(pid)}">{E(S('abstract'))}</h4>{abstract}
            </div>
            <p class="authors">{authors}</p>
            {links(actions, p['title'], 'publication-actions')}
          </div>
        </article>'''


def writing_note() -> str:
    """The blog is where the long-form working notes live. It belongs at the end
    of the writing, not only behind a footer icon."""
    note = DATA.get('writing_note')
    if not note:
        return ''
    label = tx(note, 'label', 'writing_note')
    link = anchor(note['url'], label)
    if note.get('lang'):
        link = f'<span lang="{E(note["lang"], quote=True)}">{link}</span>'
    return f'<p class="writing-note">{S("writing_note", link=link)}</p>'


def publication() -> str:
    """Peer-reviewed work and technical writing are different kinds of record,
    so each group carries its own subheading."""
    by_id = {p['id']: p for p in DATA['publications'] if p.get('publish', True)}
    names = (DATA['profile']['publication_name'], DATA['profile']['display_name'])
    blocks = []
    for group in DATA['publication_groups']:
        rows = ''.join(publication_row(by_id[pid], names) for pid in group['ids'])
        blocks.append(f'<h3 class="publication-group" id="publication-group-{E(group["id"])}">{E(tx(group, "heading", "publication group"))}</h3>'
                      f'<div class="publication-list">{rows}</div>')
    scholar = anchor('https://scholar.google.com/citations?hl=en&user=mUbKQD4AAAAJ', S('google_scholar'), 'heading-link')
    return f'''<section class="section publication shell" id="publication"><span id="research" class="anchor-alias" aria-hidden="true"></span>
      {heading(S('publication_heading'), scholar)}{''.join(blocks)}{writing_note()}</section>'''


def talks() -> str:
    approved = [t for t in DATA.get('talks', []) if t.get('publish') and t.get('publicly_shareable')]
    if not approved:
        return ''
    rows = []
    for t in approved[:DATA['talks_policy']['editorial_limit']]:
        for required in DATA['talks_policy']['required_fields']:
            if required not in t:
                raise ValueError(f'Talk {t.get("id")} lacks {required}')
        rows.append(f'<article class="talk-row"{provenance(t)}><span>{E(str(t["year"]))}</span><div><h3>{anchor(t["url"], tx(t, "title", "talk"), context=S("slides"))}</h3><p>{E(t["venue"])}</p></div></article>')
    return f'<section class="section talks shell" id="talks">{heading(S("talks_heading"))}{"".join(rows)}</section>'


def date_label(date: str | None) -> str:
    if date is None:
        return S('present')
    year, month = date[:7].split('-')
    return f'{months()[int(month) - 1]} {year}'


def background() -> str:
    jobs = []
    for j in DATA['experience']:
        dates = date_label(j['start']) + ' — ' + date_label(j['end'])
        jobs.append(f'''<article class="job"{provenance(j)}><p class="entry-date">{E(dates)}</p>
          <h4>{E(tx(j, 'title', 'experience'))}</h4><p class="job-description">{E(tx(j, 'summary', 'experience'))}</p><p class="job-focus">{E(tx(j, 'focus', 'experience'))}</p></article>''')
    degrees = []
    for e in DATA['education']:
        if not e.get('publish'):
            continue
        highlights = ''.join(f'<p>{E(s)}</p>' for s in tx(e, 'highlights_display', 'education'))
        degrees.append(f'''<article class="degree"{provenance(e)}><p class="entry-date">{E(e['start'])} — {E(e['end'])}</p>
          <h4>{E(tx(e, 'degree', 'education'))}</h4><p class="degree-grade">{E(S('gpa'))} <strong>{E(e['gpa'])}</strong> <span>{E(tx(e, 'rank', 'education'))}</span></p>
          <div class="degree-highlights">{highlights}</div></article>''')
    employer = DATA['experience'][0]
    school = DATA['education'][0]
    return f'''<section class="section background shell" id="background">
      {heading(S('background_heading'))}
      <div class="background-band" id="experience"><div class="background-label"><h3>{E(S('experience'))}</h3><p class="institution">{E(tx(employer, 'organization', 'experience'))}</p></div>
        <div class="career-entries">{''.join(jobs)}</div></div>
      <div class="background-band education-band" id="education"><div class="background-label"><h3>{E(S('education'))}</h3><p class="institution">{E(tx(school, 'institution', 'education'))}</p><p class="institution-note">{E(tx(school, 'field', 'education'))}</p></div>
        <div class="degree-grid">{''.join(degrees)}</div></div>
      <div class="community-band" id="community"{provenance(DATA['community'])}><h3>{E(S('community'))}</h3><p>{E(tx(DATA['community'], 'title', 'community'))}</p></div>
    </section>'''


def footer() -> str:
    f = DATA['footer']
    p = DATA['profile']
    subtitle = (f"{E(p['publication_name'])} · {foreign(p['name_zh'], 'zh-Hant')}<br>"
                f"{E(S('footer_role'))}")
    return f'''<footer class="quiet-footer" id="contact"><div class="shell"><div class="footer-top">
      <div><p class="footer-name">{E(p['display_name'])}</p><p class="footer-subtitle">{subtitle}</p></div>
      <div class="footer-contact"><span class="contact-label">{E(S('contact'))}</span>{anchor('mailto:' + f['email'], f['email'], 'footer-email')}</div>
      {social_links('footer')}</div>
      <div class="footer-bottom"><span>{E(S('copyright', name=p['display_name'], year=date.today().year))}</span>{anchor('#top', S('back_to_top'))}</div>
    </div></footer>'''


# --- page --------------------------------------------------------------------

# The browser chrome has to follow the palette, so theme-color is set with the
# theme rather than baked in. Both values are the `--bg` of their palette.
THEME_COLORS = {'light': '#f6f5f0', 'dark': '#111a18'}

# Runs before the stylesheet so the first paint already carries the right theme.
THEME_BOOTSTRAP = ("(function(){try{var t=localStorage.getItem('theme');"
                   "if(t!=='dark'&&t!=='light')t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';"
                   "document.documentElement.setAttribute('data-theme',t);"
                   "var m=document.querySelector('meta[name=\"theme-color\"]');"
                   "if(m&&m.dataset[t])m.content=m.dataset[t]}catch(e){}})()")


def alternates() -> str:
    if len(BUILD_LOCALES) < 2:
        return ''
    out = []
    for code in BUILD_LOCALES:
        href = CANONICAL_ORIGIN + BASE_PATH + LOCALES[code]['out'].replace('index.html', '')
        out.append(f'<link rel="alternate" hreflang="{LOCALES[code]["lang"]}" href="{E(href, quote=True)}">')
    return ''.join(out)


def page(locale: str) -> str:
    conf = LOCALES[locale]
    prefix = conf['prefix']
    canonical = CANONICAL_ORIGIN + BASE_PATH + conf['out'].replace('index.html', '')
    title = S('site_title')
    description = S('site_description')
    return f'''<!doctype html>
<html lang="{conf['lang']}" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(description, quote=True)}">
<meta name="author" content="{E(DATA['profile']['publication_name'], quote=True)}">
<meta name="theme-color" content="{THEME_COLORS['light']}" data-light="{THEME_COLORS['light']}" data-dark="{THEME_COLORS['dark']}">
<link rel="canonical" href="{E(canonical, quote=True)}">{alternates()}
<link rel="icon" href="{prefix}{FAVICON}">
<meta property="og:type" content="profile">
<meta property="og:title" content="{E(title, quote=True)}">
<meta property="og:description" content="{E(description, quote=True)}">
<meta property="og:url" content="{E(canonical, quote=True)}">
<meta property="og:image" content="{E(CANONICAL_ORIGIN + BASE_PATH + HERO_ASSET, quote=True)}">
<meta name="twitter:card" content="summary_large_image">
<script>{THEME_BOOTSTRAP}</script>
<link rel="stylesheet" href="{prefix}{CSS_OUT}">
<noscript><style>.theme-toggle{{display:none!important}}</style></noscript></head>
<body id="top"><a class="skip-link" href="#main">{E(S('skip_to_content'))}</a>{navigation()}{hero(prefix)}
<main id="main">{about(prefix)}{projects()}{competitions()}{publication()}{talks()}{background()}</main>{footer()}
<script src="{prefix}{JS_OUT}" defer></script></body></html>'''


METRIC_SHELF_LIFE_DAYS = 365


def check_metric_freshness() -> None:
    """The platform counts are hand-recorded snapshots and nothing refreshes
    them. Say so at build time rather than letting the page quietly age."""
    today = date.today()
    for group in DATA['open_source']['groups']:
        for metric in group['metrics']:
            age = (today - date.fromisoformat(metric['snapshot'])).days
            if age > METRIC_SHELF_LIFE_DAYS:
                print(f'  ! {group["platform"]} "{metric["display"]} {metric["label"]}" was recorded '
                      f'{age} days ago ({metric["snapshot"]}). Re-check it or drop the number.')


def write_assets() -> None:
    css = '\n'.join((SRC / name).read_text(encoding='utf-8') for name in ['styles.css', 'theme.css'])
    js = (SRC / 'interactions.js').read_text(encoding='utf-8')
    for target, text in [(CSS_OUT, css), (JS_OUT, js)]:
        path = ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        print(f'Wrote {target}: {len(text.encode()):,} bytes.')


def write_root_redirect() -> None:
    """Sends the deployment root to the page until something else claims it.

    The target is relative, so this works unchanged wherever the repository is
    served from: the custom domain, the workers.dev URL, GitHub Pages under
    /AboutMe/. Deliberately not a permanent redirect — browsers cache those for
    a very long time, and this one is meant to be removed the day the root has
    its own occupant.
    """
    target = LOCALES[BUILD_LOCALES[0]]['out'].replace('index.html', '')
    canonical = CANONICAL_ORIGIN + BASE_PATH + target
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(S('site_title'))}</title>
<link rel="canonical" href="{E(canonical, quote=True)}">
<meta http-equiv="refresh" content="0; url={E(target, quote=True)}">
<script>location.replace('{target}' + location.search + location.hash)</script>
<style>body{{margin:0;display:grid;place-items:center;min-height:100vh;background:#f6f5f0;color:#19342d;font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}p{{margin:0;padding:24px}}a{{color:#2f5d43}}</style>
</head>
<body><p><a href="{E(target, quote=True)}">Continue to the page</a>.</p></body>
</html>
"""
    (ROOT / 'index.html').write_text(page, encoding='utf-8')
    print(f'Wrote index.html: root redirect to /{target}')


def build(locale: str) -> None:
    global LOCALE
    LOCALE, out = locale, ROOT / LOCALES[locale]['out']
    text = page(locale)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    print(f'Built {LOCALES[locale]["out"]} [{locale}]: {len(text.encode()):,} bytes.')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', metavar='LOCALE', choices=sorted(LOCALES),
                    help='report the strings this locale still needs, and write nothing')
    args = ap.parse_args()

    if args.check:
        global LOCALE
        LOCALE = args.check
        page(args.check)
        gaps = sorted(set(MISSING))
        if not gaps:
            print(f'{args.check}: complete — add it to BUILD_LOCALES in src/build.py.')
            return
        print(f'{args.check}: {len(gaps)} string(s) still fall back to English.')
        for gap in gaps:
            print('  ' + gap)
        return

    write_assets()
    for locale in BUILD_LOCALES:
        build(locale)
    write_root_redirect()
    check_metric_freshness()


if __name__ == '__main__':
    main()
