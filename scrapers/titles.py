"""Normalize venue shout-case titles, preserving intentional mixed-case spelling."""
import re
SMALL = {'a','an','and','as','at','but','by','for','from','in','nor','of','on','or','per','the','to','vs','via','with'}
KEEP = {'Q&A','USA','US','UK','NYC','II','III','IV','VI','VII','VIII','IX','XI','XII','EC','TV','DJ','UFO','DCP'}
def title_case(title):
    if not title.isupper():
        return title
    words = title.split(' ')
    out = []
    for i, word in enumerate(words):
        bare = word.strip('():,!?“”"')
        if bare in KEEP:
            value = word
        else:
            value = re.sub(r"[\wÀ-ÿ]+(?:[’'][\wÀ-ÿ]+)*", lambda m: m[0][0].upper()+m[0][1:].lower(), word)
            if word.lower() in SMALL and i not in (0,len(words)-1) and not words[i-1].endswith((':','—','–','|')):
                value = word.lower()
        out.append(value)
    return ' '.join(out)
