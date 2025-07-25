import os
import requests
import xml.etree.ElementTree as ET

# KAM SE BUDOU SOUBORY UKLÁDAT
OUTPUT_DIR = "feeds"

# ID POŘADŮ A URL RSS
podcasts = {
    "pro-a-proti.xml": "https://api.mujrozhlas.cz/rss/podcast/0bc5da25-f081-33b6-94a3-3181435cc0a0.rss",
    "nazory-argumenty.xml": "https://api.mujrozhlas.cz/rss/podcast/f4133d64-ccb2-30e7-a70f-23e9c54d8e76.rss"
}

# vytvoř složku, pokud neexistuje
os.makedirs(OUTPUT_DIR, exist_ok=True)

for filename, url in podcasts.items():
    r = requests.get(url)
    r.raise_for_status()
    rss_text = r.text

    # načti XML
    root = ET.fromstring(rss_text)

    # ujisti se, že <channel> existuje
    channel = root.find("channel")
    if channel is None:
        channel = ET.SubElement(root, "channel")

    # přepiš nebo přidej <link>
    link_el = channel.find("link")
    if link_el is not None:
        link_el.text = f"https://novtom.github.io/rss/feeds/{filename}"
    else:
        ET.SubElement(channel, "link").text = f"https://novtom.github.io/rss/feeds/{filename}"

    # přidej description, pokud chybí
    if channel.find("description") is None:
        ET.SubElement(channel, "description").text = "RSS feed z mujRozhlas.cz"

    # ulož do souboru
    output_path = os.path.join(OUTPUT_DIR, filename)
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    print(f"✅ Vygenerováno: {output_path}")
