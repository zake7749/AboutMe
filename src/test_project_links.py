"""Check native project-card hit areas in Chromium, not remote availability.

python src/test_project_links.py [--chromium /path/to/chromium]
External clicks are recorded and cancelled in the browser test fixture only.
No test code is embedded in the shipped HTML.

Ported from the Horizon v7.2 review suite: one published page served over
loopback HTTP, with each theme seeded through localStorage rather than opened
from its own entry file.
"""
import argparse
from playwright.sync_api import sync_playwright
from qa_support import CAPTURE_CLICKS, ROOT as R, content, launch, serve, write_report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--chromium',default=None)
    args=parser.parse_args()
    data=content()
    awards={a['id']:a for a in data['awards']}
    report={'engine':'Chromium','checks':[], 'scope':'Local hover/click/keyboard/touch routing. Remote requests are not made.',
            'limitations':['No Safari/Firefox or physical iPhone test','External page availability is not a browser-test result']}
    def check(name,value,details=None):
        report['checks'].append({'name':name,'pass':bool(value),'detail':details})
        if not value: raise AssertionError(f'{name}: {details}')
    try:
        with serve() as base_url, sync_playwright() as pw:
            browser=launch(pw,args.chromium)
            for theme in ['light','dark']:
                seed=f"try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}"
                for width in [1440,390]:
                    ctx=browser.new_context(viewport={'width':width,'height':900 if width>760 else 844},
                        reduced_motion='reduce',is_mobile=width<760,has_touch=width<760)
                    ctx.add_init_script(seed)
                    page=ctx.new_page()
                    page.goto(base_url,wait_until='load')
                    assert page.locator('html').get_attribute('data-theme')==theme
                    page.evaluate(CAPTURE_CLICKS)
                    for project in data['projects']:
                        prefix=f'{theme}/{width}/{project["id"]}'
                        card=page.locator('#project-'+project['id'])
                        card.scroll_into_view_if_needed()
                        page.wait_for_timeout(30)
                        before=page.evaluate('__clicks.length')
                        desc=card.locator('.project-description')
                        box=desc.bounding_box()
                        x=box['x']+box['width']*.4;y=box['y']+box['height']*.4
                        page.mouse.move(x,y);page.wait_for_timeout(50)
                        check(prefix+': hover never navigates',page.evaluate('__clicks.length')==before and len(ctx.pages)==1)
                        page.mouse.click(x,y)
                        check(prefix+': main area opens only project',page.evaluate('__clicks.at(-1)')==project['primary_url'])
                        if project.get('competition_ref'):
                            event_link=card.locator('.project-competition-link')
                            expected=awards[project['competition_ref']]['official_url']
                            count=page.evaluate('__clicks.length')
                            if width<760:event_link.tap()
                            else:event_link.click()
                            check(prefix+': official event gets exactly one native click',
                                page.evaluate('__clicks.length')==count+1 and page.evaluate('__clicks.at(-1)')==expected)
                            check(prefix+': event hover does not underline primary title',
                                not card.locator('.primary-link').evaluate('(e)=>e.matches(":hover")'))
                            event_link.focus();page.keyboard.press('Enter')
                            check(prefix+': Enter opens official event',page.evaluate('__clicks.at(-1)')==expected)
                            card.locator('.outcome-placement').scroll_into_view_if_needed()
                            count=page.evaluate('__clicks.length')
                            card.locator('.outcome-placement').click()
                            check(prefix+': plain rank is not an invisible project link',page.evaluate('__clicks.length')==count)
                        for i,resource in enumerate(project['secondary_links']):
                            link=card.locator('.secondary-links a').nth(i)
                            count=page.evaluate('__clicks.length')
                            if width<760:link.tap()
                            else:link.click()
                            check(prefix+': resource '+resource['label']+' keeps own destination',
                                page.evaluate('__clicks.length')==count+1 and page.evaluate('__clicks.at(-1)')==resource['url'])
                    prize=page.locator('#project-kyara .project-prize')
                    check(f'{theme}/{width}: restrained prize rendered once',prize.inner_text()=='US$30,000 prize' and page.locator('.project-prize').count()==1)
                    prize.scroll_into_view_if_needed()
                    count=page.evaluate('__clicks.length');prize.click()
                    check(f'{theme}/{width}: prize is not an earnings or project link',page.evaluate('__clicks.length')==count)
                    for w in [320,360,390,430,600,760,768,1024,1440,1920]:
                        page.set_viewport_size({'width':w,'height':900})
                        check(f'{theme}/{width}: result wraps within viewport {w}',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    check(f'{theme}/{width}: no total prize pool promotion','150,000' not in page.locator('body').inner_text())
                    ctx.close()
                # The links stay native when page scripts are blocked.
                ctx=browser.new_context(java_script_enabled=False,viewport={'width':390,'height':844})
                page=ctx.new_page();page.goto(base_url,wait_until='load')
                for project in data['projects']:
                    if not project.get('competition_ref'):continue
                    link=page.locator('#project-'+project['id']+' .project-competition-link')
                    link.scroll_into_view_if_needed()
                    b=link.bounding_box()
                    hit=page.evaluate('''p => document.elementFromPoint(p.x,p.y)?.closest('a')?.href''',{'x':b['x']+b['width']/2,'y':b['y']+b['height']/2})
                    check(f'{theme}/no-js/{project["id"]}: official link is topmost native target',hit==awards[project['competition_ref']]['official_url'])
                ctx.close()
            browser.close()
    finally:
        write_report('qa-project-links',report)

if __name__=='__main__':main()
