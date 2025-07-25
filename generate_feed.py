import os
import requests
import re

# KAM SE BUDOU SOUBORY UKLÁDAT:
OUTPUT_DIR = "feeds"

# ID POŘADŮ A NÁZVY SOUBORŮ
podcasts = {
    "pro-a-proti.xml": "https://api.mujrozhlas.cz/rss/podcast/0bc5da25-f081-33b6-94a3-3181435cc0a0.rss",
    "nazory-argumenty.xml": "https://api.mujrozhlas.cz/rss/podcast/f4133d64-ccb2-30e7-a70f-23e9c54d8e76.rss"
}

# vytvoř složku, pokud neexistuje
os.makedirs(OUTPUT_DIR, exist_ok=True)

for filename, url in podcasts.items():
    r = requests.get(url)
    r.raise_for_status()
    rss = r.text

    rss = re.sub(r'https://dts\.podtrac\.com', r'http://dts.podtrac.com', rss)
    rss = re.sub(r"<title>(.*?)</title>", r"<title>\1 (LMS HTTP)</title>", rss, count=1)

    output_path = os.path.join(OUTPUT_DIR, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"✅ Vygenerováno: {output_path}")
