# generate_feed.py

import requests
import re

# Seznam podcastů: jméno souboru → URL RSS feedu
podcasts = {
    "pro-a-proti.xml": "https://api.mujrozhlas.cz/rss/podcast/0bc5da25-f081-33b6-94a3-3181435cc0a0.rss",
    "nazory-argumenty.xml": "https://api.mujrozhlas.cz/rss/podcast/f4133d64-ccb2-30e7-a70f-23e9c54d8e76.rss",
    # Přidej další pořady podle potřeby
}

for filename, url in podcasts.items():
    r = requests.get(url)
    rss = r.text

    # Přepiš https → http pouze pro mp3 linky
    rss = re.sub(r'https://dts\.podtrac\.com', r'http://dts.podtrac.com', rss)

    # Přidej poznámku do názvu (volitelné)
    rss = re.sub(r"<title>(.*?)</title>", r"<title>\1 (LMS HTTP)</title>", rss, count=1)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"Updated: {filename}")
