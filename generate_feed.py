import os
import requests
import xml.etree.ElementTree as ET

OUTPUT_DIR = "feeds"

podcasts = {
    "pro-a-proti.xml": "https://api.mujrozhlas.cz/rss/podcast/0bc5da25-f081-33b6-94a3-3181435cc0a0.rss",
    "nazory-argumenty.xml": "https://api.mujrozhlas.cz/rss/podcast/f4133d64-ccb2-30e7-a70f-23e9c54d8e76.rss",
    "vinohradska12.xml": "https://api.mujrozhlas.cz/rss/podcast/ee6095c0-33ac-3526-b8bf-df233af38211.rss",
    "Interview-plus.xml": "https://api.mujrozhlas.cz/rss/podcast/1235fcbc-baa9-3656-9488-857fca2eb987.rss",
    "Osobnost-plus.xml": "https://api.mujrozhlas.cz/rss/podcast/ad21758a-b517-328e-9bb0-2a2e2819f0b5.rss",
    "Podcasty-HN.xml": "https://www.spreaker.com/show/4194705/episodes/feed",
    "Kecy-politika.xml": "https://anchor.fm/s/99c6e0b4/podcast/rss",
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

for filename, url in podcasts.items():
    try:
        r = requests.get(url)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Chyba při stahování {url}: {e}")
        continue

    try:
        root = ET.fromstring(r.content)

        # 🧹 Odstranit <script/> pokud existuje
        for script_tag in root.findall("script"):
            root.remove(script_tag)

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

    # 🔧 Očisti <enclosure> URL: odstraň podtrac přesměrování a převeď na http
    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        if enclosure is not None and "url" in enclosure.attrib:
            url_attr = enclosure.attrib["url"]

            # Pokud začíná na podtrac redirect
            if "dts.podtrac.com/redirect.mp3/" in url_attr:
                real_url = url_attr.split("redirect.mp3/")[-1]
                # Převod na klasický http odkaz
                if real_url.startswith("https://"):
                    real_url = real_url.replace("https://", "http://", 1)
                enclosure.attrib["url"] = real_url

            # Jinak jen nahraď https → http
            elif url_attr.startswith("https://"):
                enclosure.attrib["url"] = url_attr.replace("https://", "http://", 1)

    # Výstupní cesta
    output_path = os.path.join(OUTPUT_DIR, filename)
    ET.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)

    print(f"✅ Uloženo: {output_path}")
