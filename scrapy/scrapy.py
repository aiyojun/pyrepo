import time
import asyncio
from pyppeteer import launch
from requests_html import HTMLSession
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class AsyncLooper:
    looper = asyncio.new_event_loop()

    def run(self, lamb, *args):
        return self.looper.run_until_complete(lamb(*args))


async def load_website1(url, display_window=False, proxy=None):
    """
    Use original/underlying tools(pyppeteer)
    :param url:
    :param display_window:
    :param proxy:
    :return:
    """
    launch_params = {
        'headless': False,
        'timeout': 30000,  # 30s
        'args': ['--no-sandbox', '--window-size=960,480']  # '--disable-infobars',
    } if display_window else {
        'headless': True,
        'timeout': 30000,  # 30s
        'args': ['--no-sandbox']
    }
    if proxy is not None:
        launch_params['args'].append('--proxy-server=%s' % proxy)
    print("load website, start counting, this stage may cost some time.")
    begin = int(time.time() * 1000)
    browser = await launch(launch_params)
    page = await browser.newPage()
    await page.goto(url)
    print("loading website complete, cost %d s" % (int(time.time() * 1000 - begin) / 1000))
    return await page.content()


def load_website2(url):
    """
    load a website by requests-html.
    off cause based on underlying pyppeteer too.
    :param url:
    :return:
    """
    # create an HTML Session object
    session = HTMLSession()
    # Use the object above to connect to needed webpage
    response = session.get(url)
    # Run JavaScript code on webpage
    response.html.render()
    return response.html.html


def video_task():
    looper = AsyncLooper()
    url = 'https://www.djun.xyz'

    async def _load():
        print("load website, start counting, this stage may cost some time.")
        begin = int(time.time() * 1000)
        browser = await launch({
            'headless': True, 'timeout': 30000,
            'args': ['--no-sandbox', '--proxy-server=socks5://192.168.1.201:1080']
        })
        page = await browser.newPage()
        await page.goto(url)
        print("loading website complete, cost %d s" % (int(time.time() * 1000 - begin) / 1000))
        return await page.content(), page.url

    text, url = looper.run(_load)
    soup = BeautifulSoup(text, 'lxml')
    videos = soup.find_all('video')
    print("Find (%d) videos" % len(videos))
    if len(videos) == 0:
        return
    resources = []
    for video in videos:
        src = video.get('src')
        source = video.find('source')
        src = src if src is not None else source.get('src')
        if src == '':
            continue
        if src.find('blob') == 0:
            print("blob src: %s" % src)
            continue
        if src.find('http') == 0:
            resources.append(src)
            continue
        parsed_url = urlparse(url)
        if src[0] == '/':
            resources.append("%s://%s%s" % (parsed_url.scheme, parsed_url.netloc, src))
        else:
            resources.append("%s/%s" % (url[0:url.rfind('/')], src))
    print(resources)


if __name__ == '__main__':
    video_task()
    pass
