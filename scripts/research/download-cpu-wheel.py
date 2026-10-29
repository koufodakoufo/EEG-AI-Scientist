"""Pinned official CPU wheel, resumable ranges, SHA256 from official index.

Network acquisition only; bounded to 600 seconds per invocation and four
download threads. Partial files are retained for a single explicit retry.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    wanted = 'torch-2.6.0+cpu-cp310-cp310-linux_x86_64.whl'
    index = 'https://download.pytorch.org/whl/cpu/torch/'
    with urllib.request.urlopen(index,timeout=30) as response:
        source = response.read(8*1024*1024).decode()
    links = [html.unescape(value) for value in re.findall('href="([^"]+)"',source)]
    link = next(value for value in links if urllib.parse.unquote(urllib.parse.urlsplit(value).path).endswith('/'+wanted))
    url = urllib.parse.urljoin(index,link)
    expected = urllib.parse.parse_qs(urllib.parse.urlsplit(url).fragment)['sha256'][0]
    url = url.split('#')[0]
    with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=0-0'}),timeout=30) as response:
        if response.status != 206:
            raise RuntimeError('Official CDN did not honor byte ranges')
        size = int(response.headers['Content-Range'].split('/')[-1])
        response.read(1)
    if size > 256*1024**2:
        raise ValueError('Unexpected CPU wheel size')
    manifest = {'url':url,'sha256':expected,'bytes':size,'source':index}
    (args.output/'wheel-source.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    started = time.monotonic()
    def get_part(part: int) -> None:
        start, end = size*part//4, size*(part+1)//4-1
        target = args.output/f'{wanted}.part{part}'
        have = target.stat().st_size if target.exists() else 0
        if have == end-start+1:
            return
        if have > end-start+1:
            raise ValueError('Oversized existing partial')
        request = urllib.request.Request(url,headers={'Range':f'bytes={start+have}-{end}'})
        with urllib.request.urlopen(request,timeout=25) as response, target.open('ab') as stream:
            if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start+have}-{end}/{size}':
                raise RuntimeError('Unexpected range response')
            while time.monotonic()-started < 540:
                block = response.read(min(256*1024,end-start+1-have))
                if not block:
                    break
                stream.write(block)
                have += len(block)
                if have == end-start+1:
                    break
            stream.flush()
            os.fsync(stream.fileno())
        if have != end-start+1:
            raise TimeoutError('Partial retained; transfer timebox expired')
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(get_part,range(4)))
    destination = args.output/wanted
    if destination.exists():
        raise FileExistsError('Wheel already assembled')
    digest = hashlib.sha256()
    with destination.open('xb') as stream:
        for part in range(4):
            with (args.output/f'{wanted}.part{part}').open('rb') as source_file:
                for block in iter(lambda:source_file.read(1024*1024),b''):
                    digest.update(block)
                    stream.write(block)
    if digest.hexdigest() != expected:
        raise ValueError('Official wheel SHA256 mismatch')
    print(json.dumps({**manifest,'status':'verified','elapsed_seconds':time.monotonic()-started}))


if __name__ == '__main__':
    main()
