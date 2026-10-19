#!/usr/bin/env python3
"""On-site explainers for news cards. Local CPU model (Qwen2.5-3B-Instruct Q4, llama.cpp) on the box.
Cache: data/summaries.json keyed by article URL; only new items are summarized; stale entries pruned.
Outputs with long verbatim overlap (>=10 consecutive words) with the source text are rejected (no explainer)."""
import json, os, re, sys, html, time, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data'); OUT = os.path.join(DATA, 'summaries.json')
MODEL = os.environ.get('SV_LLM', '/workspace/llm/m3.gguf')
UA = {'User-Agent': 'Mozilla/5.0 (SciVigilance explainer; +https://ciber101.github.io/SciVigilance.github.io/)'}
MAX_NEW = int(os.environ.get('SV_MAX_NEW', '120'))
BOILER = re.compile(r'(subscribe|newsletter|cookie|getty images|all rights reserved|sign up|advertis|written, fact-checked)', re.I)

def page_text(url):
    try:
        h = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read(800000).decode('utf8', 'ignore')
    except Exception:
        return ''
    h = re.sub(r'<(script|style|nav|footer|header|aside|figure)[^>]*>.*?</\1>', ' ', h, flags=re.S | re.I)
    ps = [html.unescape(re.sub(r'<[^>]+>', ' ', p)) for p in re.findall(r'<p[^>]*>(.*?)</p>', h, re.S | re.I)]
    ps = [re.sub(r'\s+', ' ', p).strip() for p in ps]
    ps = [p for p in ps if len(p) > 80 and not BOILER.search(p)]
    return ' '.join(ps)[:2200]

def words(s): return re.findall(r"[a-z0-9']+", s.lower())
def overlap(a, b, n=10):
    bw = words(b); grams = {tuple(bw[i:i+n]) for i in range(len(bw)-n+1)}
    aw = words(a); return any(tuple(aw[i:i+n]) in grams for i in range(len(aw)-n+1))

PROMPT = ("You write short explainers for a science news site. Using ONLY the facts in the source text, write 2 to 4 "
          "plain sentences in your own words: first what happened, then why it matters. Do not copy phrases from the source. "
          "Do not add any fact, number, name or claim that is not in the source. If the source says little, write only 2 short sentences. "
          "Write in the third person about the organization or researchers (never 'we' or 'our'). Keep tense exactly as the source: if something is planned, proposed or a study suggests it, say so; never state it as done or proven. No headings, no lists, no quotes, no mention of 'the article' or 'the source'.")

def main():
    t0 = time.time()
    latest = json.load(open(os.path.join(DATA, 'latest.json')))
    items = (latest.get('articles') or []) + (latest.get('ai') or []) + (latest.get('robots') or [])
    try: cache = json.load(open(OUT))
    except Exception: cache = {}
    live = {a['url'] for a in items if a.get('url')}
    cache = {u: v for u, v in cache.items() if u in live}
    todo = [a for a in items if a.get('url') and a['url'] not in cache][:MAX_NEW]
    llm = None; made = rej = 0
    for a in todo:
        src = page_text(a['url'])
        feed = a.get('summary') or ''
        text = (feed + ' ' + src).strip() if len(src) > 300 else feed
        if len(words(text)) < 25:
            cache[a['url']] = {'s': '', 'why': 'too little source text'}; continue
        if llm is None:
            from llama_cpp import Llama
            llm = Llama(model_path=MODEL, n_ctx=2048, n_threads=int(os.environ.get('SV_THREADS', '6')), verbose=False)
        msg = [{'role': 'system', 'content': PROMPT},
               {'role': 'user', 'content': f"Headline: {a['title']}\nSource text: {text}\n\nExplainer:"}]
        out = ''
        for temp in (0.3, 0.7):
            r = llm.create_chat_completion(messages=msg, temperature=temp, max_tokens=170)
            out = re.sub(r'\s+', ' ', r['choices'][0]['message']['content']).strip()
            sents = [x for x in re.split(r'(?<=[.!?])\s+', out)
                     if not re.search(r"\b(tomorrow|the article|the source|unknown)\b", x, re.I)
                     and all(n in text for n in re.findall(r'\d[\d,.]*\d|\d', x))]  # drop sentences with numbers not in source
            out = ' '.join(sents[:4])
            if out and not out.endswith(('.', '!', '?')): out = ' '.join(sents[:-1])
            if out and not overlap(out, text + ' ' + a['title']) and len(words(out)) >= 15 and not re.search(r"\b(we|our|us|we're|we’re|i)\b", out, re.I): break
            out = ''
        if out: cache[a['url']] = {'s': out}; made += 1
        else: cache[a['url']] = {'s': '', 'why': 'rejected (verbatim overlap or empty)'}; rej += 1
    json.dump(cache, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print(f'summaries: {len(cache)} cached, {made} new, {rej} rejected, {len(todo)} processed in {time.time()-t0:.0f}s')

if __name__ == '__main__':
    main()
