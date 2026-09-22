/* Progressive enhancement only. No APIs, analytics, feeds or third-party code. */
(() => {
  'use strict';
  const header = document.querySelector('.site-nav');
  const hero = document.querySelector('.hero');
  const menu = document.querySelector('.mobile-menu');
  const summary = menu?.querySelector('summary');
  const navLinks = [...document.querySelectorAll('.desktop-nav a, .mobile-nav a')];
  const sectionIds = [...new Set(navLinks.map(a => a.hash.slice(1)))];
  const sections = sectionIds.map(id => document.getElementById(id)).filter(Boolean);

  const closeMenu = (restoreFocus = false) => {
    if (!menu) return;
    menu.open = false;
    header?.classList.remove('menu-open');
    if (restoreFocus) summary?.focus();
  };
  menu?.addEventListener('toggle', () => header?.classList.toggle('menu-open', menu.open));
  navLinks.forEach(link => link.addEventListener('click', () => closeMenu()));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu?.open) closeMenu(true);
  });
  document.addEventListener('click', event => {
    if (menu?.open && !menu.contains(event.target)) closeMenu();
  });
  const desktopQuery = window.matchMedia('(min-width: 761px)');
  const onBreakpoint = event => { if (event.matches) closeMenu(); };
  if (desktopQuery.addEventListener) desktopQuery.addEventListener('change', onBreakpoint);
  else desktopQuery.addListener(onBreakpoint);


  let queued = false;
  const updateNavigation = () => {
    queued = false;
    // Sample where the text actually sits. This also handles restored scroll,
    // viewport resizing and a host viewer with a different viewport origin.
    const headerRect = header?.getBoundingClientRect();
    const headerHeight = headerRect?.height || 68;
    const sampleY = (headerRect?.top || 0) + headerHeight * .52;
    const heroRect = hero?.getBoundingClientRect();
    const onHero = Boolean(heroRect && heroRect.top <= sampleY && heroRect.bottom > sampleY);
    header?.classList.toggle('over-hero', onHero);
    // At the top the image already supplies a calm background: no filter needed.
    header?.classList.toggle('is-scrolled', Math.max(window.scrollY, 0) > 8);
    const offset = headerHeight + 135;
    let activeId = '';
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= offset) activeId = section.id;
    }
    if (window.scrollY > 0 && window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) activeId = 'contact';
    navLinks.forEach(link => {
      if (link.hash === '#' + activeId) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  const scheduleNavigation = () => {
    if (!queued) { queued = true; requestAnimationFrame(updateNavigation); }
  };
  addEventListener('scroll', scheduleNavigation, { passive: true });
  addEventListener('resize', scheduleNavigation, { passive: true });
  addEventListener('pageshow', scheduleNavigation);
  window.visualViewport?.addEventListener('resize', scheduleNavigation, { passive: true });
  window.visualViewport?.addEventListener('scroll', scheduleNavigation, { passive: true });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) scheduleNavigation();
  });
  if (typeof ResizeObserver !== 'undefined' && hero) {
    const heroObserver = new ResizeObserver(scheduleNavigation);
    heroObserver.observe(hero);
  }
  // Pin only after listeners exist. If script is blocked the native header stays
  // on the hero rather than showing a permanently wrong fixed light bar.
  header?.classList.add('nav-enhanced');
  updateNavigation();


  /* Each header has a native button whose hit area fills the non-link space.
     The title anchor sits above it; a title click never toggles the panel.
     In the non-JS document all detail content is visible and buttons are hidden. */
  document.querySelectorAll('.competition-toggle, .publication-toggle').forEach(button => {
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    const entry = button.closest('.competition, .publication-item');
    if (!panel || !entry) return;
    button.setAttribute('aria-expanded', 'false');
    panel.hidden = true;
    button.addEventListener('click', () => {
      const expanded = button.getAttribute('aria-expanded') !== 'true';
      button.setAttribute('aria-expanded', String(expanded));
      panel.hidden = !expanded;
      entry.classList.toggle('is-expanded', expanded);
      scheduleNavigation();
    });
  });
  /* One page per locale, so the switch is a native button rather than a link to
     a companion file. It changes the palette in place, preserving scroll
     position and open disclosures, and remembers the choice. Until the reader
     makes one, the page follows the operating system. A small script in <head>
     has already applied the starting theme, so there is no flash here. */
  const root = document.documentElement;
  const themeToggle = document.querySelector('[data-theme-toggle]');
  const systemDark = window.matchMedia?.('(prefers-color-scheme: dark)');
  let chosen = null;
  try { chosen = localStorage.getItem('theme'); } catch (error) { /* storage blocked */ }

  const themeColor = document.querySelector('meta[name="theme-color"]');
  const applyTheme = theme => {
    root.dataset.theme = theme;
    // The browser chrome follows the palette, not just the system setting.
    if (themeColor?.dataset[theme]) themeColor.content = themeColor.dataset[theme];
    if (!themeToggle) return;
    // The button always offers the other theme.
    const label = theme === 'dark' ? themeToggle.dataset.labelLight : themeToggle.dataset.labelDark;
    if (!label) return;
    themeToggle.setAttribute('aria-label', label);
    themeToggle.setAttribute('title', label);
  };
  applyTheme(root.dataset.theme === 'dark' ? 'dark' : 'light');
  themeToggle?.addEventListener('click', () => {
    chosen = root.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(chosen);
    try { localStorage.setItem('theme', chosen); } catch (error) { /* storage blocked */ }
    scheduleNavigation();
  });
  systemDark?.addEventListener?.('change', event => {
    if (chosen === 'dark' || chosen === 'light') return;
    applyTheme(event.matches ? 'dark' : 'light');
    scheduleNavigation();
  });
  document.documentElement.classList.add('js');
  const revealHash = () => {
    const id = location.hash.slice(1);
    if (!id) return;
    const target = document.getElementById(id);
    const panel = target?.closest('.competition-detail, .publication-detail');
    if (panel?.hidden) {
      const button = document.querySelector(`button[aria-controls="${panel.id}"]`);
      button?.click();
      target.scrollIntoView();
    }
    scheduleNavigation();
  };
  addEventListener('hashchange', revealHash);
  updateNavigation();
  revealHash();
})();
