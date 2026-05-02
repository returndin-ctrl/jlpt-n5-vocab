#!/usr/bin/env python3
"""Pre-generate anime-style Pollinations images for ALL N5 words.

Reads WORDS, WORD_EN, WORD_AI from index.html. For each word id that does
not yet have a usable images/{id}.jpg, builds a prompt and downloads.

Prompt priority:
  1. WORD_AI[id]  (hand-crafted prompt for abstract words)
  2. WORD_EN[id]  (English search term)
  3. fallback: "{meaning}" stripped of CJK noise

A consistent anime style suffix is appended so cards look uniform.
Safe to re-run — skips existing non-tiny files.
"""
import re
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(ROOT, 'index.html')
OUT = os.path.join(ROOT, 'images')
os.makedirs(OUT, exist_ok=True)

STYLE = ', anime style illustration, kawaii, soft pastel colors, clean simple background, cute'
DELAY = 15.0  # seconds between requests (Pollinations anon: 1 in queue at a time)

text = open(HTML, encoding='utf-8').read()


def extract_block(name):
    m = re.search(r'const ' + name + r' = \{(.*?)\n\};', text, re.S)
    if not m:
        sys.exit(f'{name} block not found')
    return m.group(1)


def parse_str_map(block):
    out = {}
    for m in re.finditer(r"(\d+)\s*:\s*'([^']+)'", block):
        out[int(m.group(1))] = m.group(2)
    return out


WORD_AI = parse_str_map(extract_block('WORD_AI'))
WORD_EN = parse_str_map(extract_block('WORD_EN'))

# Parse WORDS array entries: capture id, kanji, meaning
words_match = re.search(r'const WORDS = \[(.*?)\n\];', text, re.S)
if not words_match:
    sys.exit('WORDS array not found')
words_block = words_match.group(1)

WORDS = []
for m in re.finditer(
    r'\{\s*id:(\d+)\s*,\s*k:"([^"]+)"\s*,\s*r:"[^"]*"\s*,\s*m:"([^"]+)"',
    words_block,
):
    WORDS.append((int(m.group(1)), m.group(2), m.group(3)))

print(f'Parsed {len(WORDS)} words, {len(WORD_AI)} WORD_AI, {len(WORD_EN)} WORD_EN')


def clean_meaning(m):
    # take first segment before 、 or , and strip parens
    seg = re.split(r'[、,，]', m)[0]
    seg = re.sub(r'[（(].*?[)）]', '', seg).strip()
    return seg


def build_prompt(wid, kanji, meaning):
    if wid in WORD_AI:
        base = WORD_AI[wid]
    elif wid in WORD_EN:
        base = WORD_EN[wid]
    else:
        base = clean_meaning(meaning) or kanji
    return base + STYLE


def url_for(prompt, seed):
    q = urllib.parse.quote(prompt, safe='')
    return (f'https://image.pollinations.ai/prompt/{q}'
            f'?width=512&height=512&nologo=true&seed={seed}&model=turbo')


def download(wid, prompt):
    out = os.path.join(OUT, f'{wid}.jpg')
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return 'cached'
    seed = wid * 100 + 1
    u = url_for(prompt, seed)
    last_err = 'unknown'
    for attempt in range(8):
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) < 1000:
                return f'too-small ({len(data)})'
            with open(out, 'wb') as f:
                f.write(data)
            return f'ok ({len(data)//1024}KB)'
        except urllib.error.HTTPError as e:
            last_err = f'http {e.code}'
            wait = min(5 * (2 ** attempt), 120) if e.code == 429 else 3
            time.sleep(wait)
        except Exception as e:
            last_err = f'err: {e}'
            time.sleep(3)
    return last_err


todo = []
for wid, k, m in WORDS:
    out = os.path.join(OUT, f'{wid}.jpg')
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        continue
    todo.append((wid, k, m))

print(f'{len(todo)} images to generate (skipping {len(WORDS) - len(todo)} cached)')

start = time.time()
for i, (wid, k, m) in enumerate(todo, 1):
    prompt = build_prompt(wid, k, m)
    status = download(wid, prompt)
    elapsed = time.time() - start
    print(f'[{i}/{len(todo)}] id={wid} k={k!r} {status}  (t={elapsed:.0f}s)', flush=True)
    if not status.startswith('cached') and not status.startswith('err') and not status.startswith('http'):
        time.sleep(DELAY)

print(f'Done in {time.time()-start:.0f}s')
