import json
import os
import time
import asyncio
from argparse import ArgumentParser
from urllib.parse import urlparse
from pyppeteer import launch
from pyppeteer.launcher import Launcher
from pyppeteer.network_manager import Request, Response


# pyppeteer: python api of puppeteer (node.js)
# The ibrowser is not prepared for scrapy purposes.
# For better hack website, and build a transparent
# browser to research website.
# For avoiding data grabbing, some websites used
# special solutions. So, we can't research the source
# code.
from pyppeteer.page import Page

parser = ArgumentParser(description="Browser hacking.")
parser.add_argument("-u", "--url", default=None)
parser.add_argument("-w", "--window", action="store_true")
parser.add_argument("-s", "--sandbox", action="store_false", default=True,
                    help="Append [--no-sandbox] option to chromium")
parser.add_argument("-p", "--proxy", default=None)
parser.add_argument("-t", "--timeout", default=30, help="Navigator timeout in seconds")
parser.add_argument("-a", "--agent", default='none', choices=['firefox', 'chrome', 'none'])
args = parser.parse_args()


launcher_params = {'headless': True, 'timeout': int(args.timeout) * 1000, 'args': []}
if args.window:
    launcher_params['headless'] = False
    launcher_params['args'].append('--window-size=960,480')
if args.proxy is not None:
    launcher_params['args'].append('--proxy-server=%s' % args.proxy)
if args.sandbox:
    launcher_params['args'].append('--no-sandbox')


def dumps(js: dict):
    print(json.dumps(js))


async def _hk_responses(response: Response, page: Page):
    request = response.request
    parsed_web = urlparse(page.url)
    parsed_url = urlparse(request.url)
    dumps({
        # 'time': int(time.time() * 1000),
        # 'metaType': 'response',
        'method': request.method,
        'resourceType': request.resourceType,
        'url': request.url,
        'host': parsed_web.hostname,
        'path': parsed_url.path,
        'headers': request.headers,
        # 'body': request.postData,
        'status': response.status,
    })


async def _hk_target(target, state, browser=None):
    if target.type == 'page' and state == 'created':
        pages = await browser.pages()
        print('Binding response listener on %s' % pages[-1].url)
        pages[-1].on("response", lambda x: asyncio.ensure_future(_hk_responses(x, pages[-1])))
    elif state == 'destroyed':
        print('Close %s %s' % (target.type, target.url))
    if target.type == 'page':
        parser_url = urlparse(target.url)
        if parser_url.scheme in ['http', 'https']:
            print("- [%s] page %s" % (state, target.url))
    pass


async def hack():
    global launcher_params
    print("Open browser with parameters: %s" % json.dumps(launcher_params))
    launcher = Launcher(launcher_params)
    browser = await launcher.launch()
    browser.on("targetcreated", lambda x: asyncio.ensure_future(_hk_target(x, 'created', browser)))
    browser.on("targetchanged", lambda x: asyncio.ensure_future(_hk_target(x, 'changed')))
    browser.on("targetdestroyed", lambda x: asyncio.ensure_future(_hk_target(x, 'destroyed')))
    print("browser listener")
    print(args.url)
    if args.url is not None:
        print("open page %s" % args.url)
        page = await browser.newPage()
        if args.agent != '':
            _user_agent = "Mozilla/5.0 (X11; Linux x86_64; rv:85.0) Gecko/20100101 Firefox/85.0" \
                if args.agent == 'firefox' else 'Mozilla/5.0 (X11; Linux x86_64) ' \
                                                'AppleWebKit/537.36 (KHTML, like Gecko) ' \
                                                'Chrome/91.0.4472.114 Safari/537.36'
            await page.setUserAgent(_user_agent)
        page.on("response", lambda x: asyncio.ensure_future(_hk_responses(x, page)))
        await page.goto(args.url)
        await page.waitFor(180000)

    # launcher.waitForChromeToClose()
    # input("Type any key to exit...")
    pass


if __name__ == '__main__':
    print('hacking...')
    asyncio.get_event_loop().run_until_complete(hack())
    print('hacking over')
