"""Conservative TMDB still lookup. Requires a server-side TMDB_READ_TOKEN."""
import json, os, re, unicodedata, urllib.parse, urllib.request

def title_key(title):
    title = re.split(r'\s+\||\s+\+\s*Q&A|\s*\(Open Captioning\)', title, flags=re.I)[0]
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', title).encode('ascii','ignore').decode().lower())

def api(path, **params):
    token = os.environ.get('TMDB_READ_TOKEN')
    if not token: return {}
    url = 'https://api.themoviedb.org/3/' + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization':'Bearer '+token, 'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

def candidates(row):
    """Never choose a remake or ambiguous title purely by search popularity."""
    title = re.split(r'\s+\||\s+\+\s*Q&A|\s*\(Open Captioning\)', row['title'], flags=re.I)[0]
    matches = []
    for movie in api('search/movie', query=title, include_adult='false').get('results', []):
        if title_key(title) not in {title_key(movie.get('title','')), title_key(movie.get('original_title',''))}: continue
        year = str(row.get('year') or '')
        if year and movie.get('release_date','')[:4] != year: continue
        director = row.get('director')
        if director:
            crew = api(f"movie/{movie['id']}/credits").get('crew', [])
            names = [title_key(p['name']) for p in crew if p.get('job') == 'Director']
            expected = title_key(director)
            if not any(name and name in expected for name in names): continue
        elif not year:
            continue  # No corroborating identity: leave it for review.
        matches.append(movie)
    if len(matches) != 1: return []
    movie = matches[0]
    images = api(f"movie/{movie['id']}/images").get('backdrops', [])
    images = [i for i in images if i.get('width',0)>=720 and i.get('height',0)>=400 and i.get('iso_639_1') is None]
    images.sort(key=lambda i:(i.get('vote_average',0),i.get('vote_count',0),i['width']), reverse=True)
    return [{'sourceUrl':'https://image.tmdb.org/t/p/w1280'+i['file_path'],
             'sourcePage':f"https://www.themoviedb.org/movie/{movie['id']}",
             'provider':'TMDB','tmdbId':movie['id']} for i in images[:3]]
