import os
import requests
import xml.etree.ElementTree as ET

OUTPUT_DIR = "feeds"

podcasts = {
    "pro-a-proti.xml": "https://api.mujrozhlas.cz/rss/podcast/0bc5da25-f081-33b6-94a3-3181435cc0a0.rss",
    "nazory-argumenty.xml": "https://api.mujrozhlas.cz/rss/podcast/f4133d64-ccb2-30e7-a70f-23e9c54d8e76.rss"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

for filename, url in podcasts.items():
    try:
        r = requests.get(url)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Chyba při stahování {url}: {e}")
        continue

    # Oprava "podcast://https" → "https"
    rss_fixed = r.text.replace("podcast://https", "https").replace("podcast://http", "http")

    try:
        root = ET.fromstring(rss_fixed)
    except ET.ParseError as e:
        print(f"❌ Chyba při parsování XML z {url}: {e}")
        continue

    if root.tag != "rss":
        print(f"❌ Kořenový element není <rss> v {filename}")
        continue

    channel = root.find("channel")
    if channel is None:
        print(f"❌ Nenalezen <channel> v {filename}")
        continue

    # Uprav <link>
    link = channel.find("link")
    if link is not None:
        link.text = f"https://novtom.github.io/rss/feeds/{filename}"
    else:
        ET.SubElement(channel, "link").text = f"https://novtom.github.io/rss/feeds/{filename}"

    # Přidej description, pokud chybí
    if channel.find("description") is None:
        ET.SubElement(channel, "description").text = "RSS feed z mujRozhlas.cz"

    # Výstupní cesta
    output_path = os.path.join(OUTPUT_DIR, filename)
    ET.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)

    print(f"✅ Uloženo: {output_path}")
