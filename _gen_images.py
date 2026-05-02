#!/usr/bin/env python3
"""Pre-generate Pollinations AI images for abstract words and save to images/.
Reads WORD_AI map from index.html, hits Pollinations for each entry with the
seed the JS would use (id*100 + 1), downloads to images/{id}.jpg.
"""
import re
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(ROOT, 'index.html')
OUT = os.path.join(ROOT, 'images')
os.makedirs(OUT, exist_ok=True)

# Extract WORD_AI block
text = open(HTML, encoding='utf-8').read()
m = re.search(r'const WORD_AI = \{(.*?)\n\};', text, re.S)
if not m:
    sys.exit('WORD_AI block not found')
block = m.group(1)

# Parse "id:'prompt'," entries (allow whitespace, multiple per line)
entries = re.findall(r"(\d+)\s*:\s*'([^']+)'", block)
print(f'Found {len(entries)} AI entries')

def url_for(id_, prompt, seed):
    q = urllib.parse.quote(prompt, safe='')
    return (f'https://image.pollinations.ai/prompt/{q}'
            f'?width=512&height=512&nologo=true&seed={seed}&model=turbo')

def download(item):
    id_, prompt = item
    out = os.path.join(OUT, f'{id_}.jpg')
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return id_, 'cached'
    seed = int(id_) * 100 + 1
    u = url_for(id_, prompt, seed)
    last_err = 'unknown'
    for attempt in range(8):
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) < 1000:
                return id_, f'too-small ({len(data)})'
            with open(out, 'wb') as f:
                f.write(data)
            return id_, f'ok ({len(data)//1024}KB)'
        except urllib.error.HTTPError as e:
            last_err = f'http {e.code}'
            if e.code == 429:
                wait = min(5 * (2 ** attempt), 120)
                time.sleep(wait)
            else:
                time.sleep(3)
        except Exception as e:
            last_err = f'err: {e}'
            time.sleep(3)
    return id_, last_err

start = time.time()
done = 0
DELAY = 15.0  # seconds between requests, to avoid 429 (anonymous tier: 1 in queue at a time)
for e in entries:
    try:
        result = download(e)
        if result is None:
            id_, status = e[0], 'no-return'
        else:
            id_, status = result
    except Exception as ex:
        id_, status = e[0], f'crash: {ex}'
    done += 1
    elapsed = time.time() - start
    print(f'[{done}/{len(entries)}] id={id_} {status}  (t={elapsed:.1f}s)', flush=True)
    if status != 'cached' and not status.startswith('err') and not status.startswith('crash'):
        time.sleep(DELAY)

print(f'Done in {time.time()-start:.1f}s')
