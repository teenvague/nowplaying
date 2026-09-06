"""Add a concise source-derived sentence to each screening."""
from __future__ import annotations
import concurrent.futures, html, json, re, urllib.request
from pathlib import Path
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
VENUES={v['id']:v for v in json.loads((ROOT/'dist/data/theaters.json').read_text())}

def clean(value):
    value=html.unescape(re.sub(r'\s+',' ',value or '')).strip(' \n\t“”')
    parts=re.split(r'(?<=[.!?])\s+',value,maxsplit=1)
    sentence=parts[0].strip()
    if len(sentence)>230: sentence=sentence[:227].rsplit(' ',1)[0]+'…'
    elif sentence and sentence[-1] not in '.!?…': sentence+='.'
    return sentence

def cache_maps(source_dir):
    from bs4 import BeautifulSoup
    base=Path(source_dir); maps={}
    def add(venue,url,value):
        value=clean(value)
        if value: maps[(venue,url)]=value
    s=BeautifulSoup((base/'metrograph.html').read_text(),'html.parser')
    for item in s.select('.homepage-in-theater-movie'):
        link=item.select_one('.movie_title a'); synopsis=item.select_one('.synopsis')
        if link and synopsis:add('metrograph',urljoin(VENUES['metrograph']['sourceUrl'],link.get('href','')),synopsis.get_text(' ',strip=True))
    s=BeautifulSoup((base/'roxy.html').read_text(),'html.parser')
    for item in s.select('.detailed-screening__card'):
        link=item.select_one('a.cta--text-link'); copy=item.select_one('.detailed-screening__copy')
        if link and copy:add('roxy',link.get('href',''),copy.get_text(' ',strip=True))
    s=BeautifulSoup((base/'anthology-list.html').read_text(),'html.parser')
    for item in s.select('.film-showing'):
        anchor=item.find('a',attrs={'name':re.compile('^showing-')}); note=item.select_one('.film-notes p')
        if anchor and note:add('anthology',VENUES['anthology']['sourceUrl']+'?view=list#'+anchor['name'],note.get_text(' ',strip=True))
    for record in json.loads((base/'bam-api.json').read_text()):
        if record.get('genres')=='Film':add('bam',urljoin(VENUES['bam']['sourceUrl'],record.get('moreLink','')),record.get('desc',''))
    return maps

def extract_page(raw,url):
    s=BeautifulSoup(raw,'html.parser')
    selectors=['.synopsis','.film-text-content.synopsis','.film-notes p','.detailed-screening__copy','.description','.film-description','.field-name-body p','.entry-content p','.content p']
    for selector in selectors:
        for node in s.select(selector):
            value=clean(node.get_text(' ',strip=True))
            if len(value)>=45:return value
    meta=s.select_one('meta[property="og:description"]') or s.select_one('meta[name="description"]')
    value=clean(meta.get('content','') if meta else '')
    generic=('Established in 1972','Experience cinema','See what’s now playing')
    return '' if any(value.startswith(x) for x in generic) else value

def enrich_descriptions(data,source_dir=None):
    maps=cache_maps(source_dir) if source_dir else {}
    need={r['ticketUrl'] for r in data['screenings'] if not r.get('description') and (r['venue'],r['ticketUrl']) not in maps}
    def fetch(url):
        try:
            req=urllib.request.Request(quote(url,safe=':/?&=%+#'),headers={'User-Agent':'PlayingInNewYork/1.0 (cinema calendar index)'})
            with urllib.request.urlopen(req,timeout=20) as response:raw=response.read().decode('utf-8',errors='replace')
            return url,extract_page(raw,url)
        except Exception:return url,''
    if need:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: fetched=dict(pool.map(fetch,need))
    else:fetched={}
    for row in data['screenings']:
        desc=row.get('description') or maps.get((row['venue'],row['ticketUrl'])) or fetched.get(row['ticketUrl'])
        if not desc:
            who=(row.get('director')+'’s ') if row.get('director') else ''
            year=(' '+str(row['year'])) if row.get('year') else ''
            desc=f"{who}{year.strip()+' ' if year else ''}{row['title']} screens at {VENUES[row['venue']]['name']}."
        row['description']=clean(desc)
    return data

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--source-dir');args=a.parse_args()
    path=ROOT/'dist/data/screenings.json';d=json.loads(path.read_text());d=enrich_descriptions(d,args.source_dir);path.write_text(json.dumps(d,ensure_ascii=False,indent=2))
