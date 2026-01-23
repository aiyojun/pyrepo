# Copyright 2022-present aiyojun. All rights reserved.

import os
import time
import shutil
import logging
import argparse
from urllib.parse import urlparse

import m3u8
import requests
import threadpool
from Crypto.Cipher import AES

# 1. get m3u8
# 2. get key if encrypted
# 3. download ts
# 4. merge ts


def arg_help():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url', required=True, help='url of m3u8 file')
    parser.add_argument('-f', '--filename', default='video', help='output video filename')
    parser.add_argument('-c', '--cache', default='cache-ts', help='temporary cache')
    parser.add_argument('-t', '--thread_number', default=20, help='thread number of downloading')
    return parser.parse_args()


logging.basicConfig(
    format='%(message)s',
    level=logging.INFO
)
args = arg_help()
cache_dir = args.cache  # 'cache-ts' default


def _worker(self, ts_link, ts_index):
    global cache_dir
    count = 1
    file_path = "%s/video.%d.ts" % (cache_dir, ts_index)
    if os.path.exists(file_path):
        os.remove(file_path)
    fp = open(file_path, 'wb+')
    ts_url = ts_link if ts_link.startswith('http') else "%s/%s" % (self.location, ts_link)
    while True:
        try:
            if count >= 10:
                logging.warning("Request many times! %s" % ts_url)
            response = requests.get(ts_url, timeout=self.timeout, headers=self.headers, stream=True)
            if response.status_code != 200:
                count += 1
                continue
            binary = response.content
            # logging.info("  >> video.%d.ts" % ts_index)
            self.last_time = self.record_time
            self.last_bytes = self.record_bytes
            self.record_time = int(time.time() * 1000)
            self.record_bytes += len(binary)
            fp.write(binary)
            self.completed_segments += 1
            break
        except Exception as e:
            logging.error('Net error : %s' % str(e))
    fp.close()


class Composer:
    timeout = 20
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8," +
                  "application/signed-exchange;v=b3;q=0.9",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " +
                      "Chrome/85.0.4183.102 Safari/537.36 "
    }
    crypto = None
    location = ''
    total_segments = 0
    completed_segments = 0
    last_time = 0
    last_bytes = 0
    record_time = 0
    record_bytes = 0

    def __init__(self):
        pass

    def _download(self, url, max_redirect=3):
        real_url, m3u8text = url, None
        redirect_count = 1
        while redirect_count <= max_redirect:
            if redirect_count == max_redirect:
                logging.warning('Redirect too many times')
            try:
                response = requests.get(real_url, headers=self.headers, timeout=self.timeout)
                if response.status_code == 301:
                    real_url = response.headers['location']
                    redirect_count += 1
                    continue
                m3u8text = response.text
                break
            except Exception as e:
                raise Exception('Net error when download resource(%s) : %s' % (url, str(e)))
        if m3u8text is None:
            raise Exception('Download failed! empty resource(%s)' % url)
        self.location = real_url[0:real_url.rindex('/')]
        return m3u8text

    def parse_m3u8(self, m3u8url):
        m3u8text = self._download(m3u8url)
        playlist = m3u8.loads(m3u8text)
        if not playlist.is_variant:
            return playlist
        for row in m3u8text.split('\n'):
            if row.endswith('m3u8'):
                parsed_url = urlparse(m3u8url)
                return self.parse_m3u8("%s://%s%s" % (parsed_url.scheme, parsed_url.netloc, row))
        raise Exception('multi code stream cannot find m3u8 file')

    def decrypt(self, playlist):
        if len(playlist.keys) == 0 or playlist.keys[0] is None:
            return
        m3u8key = playlist.keys[0]
        if m3u8key.method != 'AES-128':
            raise Exception('Only AES-128 support, but %s' % m3u8key.method)
        logging.info("Satisfy AES-128")
        key_url = m3u8key.uri if m3u8key.uri.startswith('http') else "%s/%s" % (self.location, m3u8key.uri)
        key_text, _ = self._download(key_url)
        iv = m3u8key.iv if m3u8key.iv is not None else key_text
        self.crypto = AES.new(bytes(key_text, encoding='utf8'), AES.MODE_CBC, bytes(iv, encoding='utf8'))

    def merge(self, total, output_path):
        if os.path.exists(output_path):
            os.remove(output_path)
        fp = open(output_path, 'wb+')
        for i in range(total):
            try:
                ts_file = open("cache-ts/video.%d.ts" % i, 'rb')
                _data = ts_file.read()
                fp.write(_data if self.crypto is None else self.crypto.decrypt(_data))
                ts_file.close()
            except Exception as e:
                raise e
        fp.close()

    def load(self, m3u8url, output_path="video.ts", thread_number=20):
        logging.info("Loading %s" % m3u8url)
        playlist = self.parse_m3u8(m3u8url)
        self.decrypt(playlist)
        tasks = []
        for i in range(len(playlist.segments)):
            seg = playlist.segments[i]
            tasks.append(([self, seg.uri, i], None))
        self.total_segments = len(tasks)
        self.completed_segments = 0
        begin = int(time.time() * 1000)
        self.record_time = begin
        self.last_time = self.record_time
        pool = threadpool.ThreadPool(thread_number)
        reqs = threadpool.makeRequests(_worker, tasks)
        global cache_dir
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        os.mkdir(cache_dir)
        logging.info("Multi-thread (%d) downloading" % thread_number)
        [pool.putRequest(req) for req in reqs]
        while self.completed_segments < self.total_segments:
            if self.record_time > self.last_time:
                logging.info('speed %f M/s, %d / %d' % (
                    (self.record_bytes - self.last_bytes) * 1000 / (self.record_time - self.last_time) / 1024 / 1024,
                    self.completed_segments, self.total_segments,
                ))
            time.sleep(1)
        logging.info("size : %d M, cost : %d s" %
                     (self.record_bytes / 1024 / 1024, (self.record_time - begin) / 1000.0))
        self.merge(len(tasks), output_path)
        shutil.rmtree('cache-ts')


if __name__ == '__main__':
    # Test url:
    #   "http://1257120875.vod2.myqcloud.com/0ef121cdvodtransgzp1257120875/3055695e5285890780828799271/v.f230.m3u8"
    try:
        composer = Composer()
        composer.load(
            args.url,
            "%s.ts" % args.filename,
            int(args.thread_number)
        )
    except Exception as e:
        logging.error(str(e))
