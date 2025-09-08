import os
import requests
import xml.etree.ElementTree as ET
import base64
from urllib.parse import urlparse



OUTPUT_DIR = "feeds"

podcasts = {
    "pro-a-proti.xml": "https://api.mujrozhlas.cz/rss/podcast/0bc5da25-f081-33b6-94a3-3181435cc0a0.rss",
    "nazory-argumenty.xml": "https://api.mujrozhlas.cz/rss/podcast/f4133d64-ccb2-30e7-a70f-23e9c54d8e76.rss",
    "vinohradska12.xml": "https://api.mujrozhlas.cz/rss/podcast/ee6095c0-33ac-3526-b8bf-df233af38211.rss",
    "Interview-plus.xml": "https://api.mujrozhlas.cz/rss/podcast/1235fcbc-baa9-3656-9488-857fca2eb987.rss",
    "Osobnost-plus.xml": "https://api.mujrozhlas.cz/rss/podcast/ad21758a-b517-328e-9bb0-2a2e2819f0b5.rss",
    "Podcasty-HN.xml": "https://www.spreaker.com/show/4194705/episodes/feed",
    "Kecy-politika.xml": "https://anchor.fm/s/99c6e0b4/podcast/rss",
    "Chyba-systemu.xml": "https://api.mujrozhlas.cz/rss/podcast/47833fff-1845-3b97-b263-54fe2c4026b7.rss",
    "Ceska-satira.xml": "https://api.mujrozhlas.cz/rss/podcast/4c2d5141-ad8d-3e73-b041-45170e6e1255.rss",
    "Vojta-zizka.xml": "https://anchor.fm/s/763bc3a8/podcast/rss",
    "Mezi-rentiery.xml": "https://audioboom.com/channels/5096524.rss",
    "Brain-we-are.xml": "https://anchor.fm/s/7330de0/podcast/rss",
    "Fantastic-future.xml": "https://anchor.fm/s/102799d7c/podcast/rss",
    "5-59.xml": "https://feeds.transistor.fm/5-59",
    "xtb.xml": "https://anchor.fm/s/3de2cbdc/podcast/rss",
    "kilometry.xml": "https://api.mujrozhlas.cz/rss/podcast/b2b82381-216d-310e-aeef-d46cd919d15d.rss",
    "ruz_vor.xml": "https://anchor.fm/s/f5e22098/podcast/rss",
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

    # 🔻 Omez počet epizod v RSS feedu
    items = channel.findall("item")
    max_items = 100  # změň podle potřeby (např. 200)
    for item in items[max_items:]:
        channel.remove(item)

    
    # Uprav <link>
    link = channel.find("link")
    if link is not None:
        link.text = f"https://novtom.github.io/rss/feeds/{filename}"
    else:
        ET.SubElement(channel, "link").text = f"https://novtom.github.io/rss/feeds/{filename}"

    # Přidej <description> pokud chybí
    if channel.find("description") is None:
        ET.SubElement(channel, "description").text = "RSS feed z mujRozhlas.cz"
    # 🖼️ Doplnění obrázků pro klienty, co nečtou itunes:image
    ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
    MRSS_NS = "http://search.yahoo.com/mrss/"

    # 1) CHANNEL IMAGE: když chybí <image>, vezmeme ho z <itunes:image href="...">
    rss_image = channel.find("image")
    itunes_image = channel.find(f"{{{ITUNES_NS}}}image")
    if rss_image is None and itunes_image is not None and "href" in itunes_image.attrib:
        img = ET.SubElement(channel, "image")
        ET.SubElement(img, "url").text = itunes_image.attrib["href"]  # necháme HTTPS; u obrázků to bývá OK
        ET.SubElement(img, "title").text = channel.findtext("title") or "Podcast"
        # vezmeme už tebou nastavený channel <link>, nebo fallback na GH Pages
        ch_link = channel.findtext("link") or f"https://novtom.github.io/rss/feeds/{filename}"
        ET.SubElement(img, "link").text = ch_link

    # 2) ITEM THUMBNAILS: přidej <media:thumbnail url="..."> z <itunes:image>, pokud není
    for item in channel.findall("item"):
        it_img = item.find(f"{{{ITUNES_NS}}}image")
        has_thumb = item.find(f"{{{MRSS_NS}}}thumbnail") is not None
        if it_img is not None and ("href" in it_img.attrib) and not has_thumb:
            thumb = ET.SubElement(item, f"{{{MRSS_NS}}}thumbnail")
            thumb.set("url", it_img.attrib["href"])
    # 🖼️ Per-item title & image fallbacky (pro LMS)
    ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
    MRSS_NS = "http://search.yahoo.com/mrss/"

    # Zjisti URL obrázku na úrovni kanálu (použijeme jako fallback)
    channel_img_url = None
    ch_img_el = channel.find("image")
    if ch_img_el is not None:
        channel_img_url = (ch_img_el.findtext("url") or "").strip() or None
    if not channel_img_url:
        ch_it_img = channel.find(f"{{{ITUNES_NS}}}image")
        if ch_it_img is not None:
            channel_img_url = ch_it_img.attrib.get("href")

    # Pro každé <item>:
    for item in channel.findall("item"):
        # 1) TITLE: pokud chybí <title>, vezmi itunes:title nebo description
        title_el = item.find("title")
        if title_el is None or (title_el.text or "").strip() == "":
            it_title = item.find(f"{{{ITUNES_NS}}}title")
            new_title = None
            if it_title is not None and (it_title.text or "").strip():
                new_title = it_title.text.strip()
            else:
                desc = item.findtext("description", "").strip()
                if desc:
                    # usekni na rozumnou délku
                    new_title = (desc.replace("\n", " ").strip())[:140]
            if new_title:
                ET.SubElement(item, "title").text = new_title

        # 2) IMAGE: pokud nemá epizoda svůj obrázek, doplň z kanálu
        has_it_img = item.find(f"{{{ITUNES_NS}}}image") is not None
        has_mrss_thumb = item.find(f"{{{MRSS_NS}}}thumbnail") is not None
        if channel_img_url and not (has_it_img or has_mrss_thumb):
            # a) itunes:image
            it_img = ET.SubElement(item, f"{{{ITUNES_NS}}}image")
            it_img.set("href", channel_img_url)
            # b) media:thumbnail
            thumb = ET.SubElement(item, f"{{{MRSS_NS}}}thumbnail")
            thumb.set("url", channel_img_url)

        # 🧩 Per-item fallbacky na title a artwork
    # Zjisti kanálový artwork jako fallback
    channel_img_url = None
    ch_img_el = channel.find("image")
    if ch_img_el is not None:
        channel_img_url = (ch_img_el.findtext("url") or "").strip() or None
    if not channel_img_url:
        ch_it_img = channel.find(f"{{{ITUNES_NS}}}image")
        if ch_it_img is not None:
            channel_img_url = ch_it_img.attrib.get("href")

    for item in channel.findall("item"):
        # 1) itunes:title – pokud chybí, vytvoř ho (z <title> nebo fallback)
        it_title = item.find(f"{{{ITUNES_NS}}}title")
        if it_title is None:
            base_title = (item.findtext("title") or "").strip()
            if not base_title:
                # poslední pojistka z description (zkráceně)
                base_title = (item.findtext("description") or "").strip().replace("\n", " ")
                base_title = base_title[:140] if base_title else "Episode"
            ET.SubElement(item, f"{{{ITUNES_NS}}}title").text = base_title

        # 2) Obrázek na položce: pokud chybí, doplň itunes:image + media:thumbnail z kanálu
        has_it_img = item.find(f"{{{ITUNES_NS}}}image") is not None
        has_media_thumb = item.find(f"{{{MRSS_NS}}}thumbnail") is not None
        if channel_img_url and not (has_it_img or has_media_thumb):
            it_img = ET.SubElement(item, f"{{{ITUNES_NS}}}image")
            it_img.set("href", channel_img_url)
            thumb = ET.SubElement(item, f"{{{MRSS_NS}}}thumbnail")
            thumb.set("url", channel_img_url)
    # 🔧 Úprava <enclosure> URL
    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        if enclosure is not None and "url" in enclosure.attrib:
            url_attr = enclosure.attrib["url"]

            # 1️⃣ Podtrac redirect
            if "dts.podtrac.com/redirect.mp3/" in url_attr:
                url_attr = url_attr.replace("https://dts.podtrac.com/redirect.mp3/", "")

            # 2️⃣ Base64 zakódovaný mujRozhlas
            parsed = urlparse(url_attr)
            if "aod" in parsed.path and parsed.path.endswith(".mp3"):
                try:
                    b64name = parsed.path.split("/")[-1].replace(".mp3", "")
                    decoded_url = base64.urlsafe_b64decode(b64name + "==").decode("utf-8")
                    if decoded_url.startswith("https://"):
                        decoded_url = decoded_url.replace("https://", "http://", 1)
                    if not decoded_url.startswith(("http://", "https://")):
                        decoded_url = "http://" + decoded_url
                    enclosure.attrib["url"] = decoded_url
                except Exception as e:
                    print(f"❌ Base64 decode fail: {e} (u {url_attr})")
                    if url_attr.startswith("https://"):
                        enclosure.attrib["url"] = url_attr.replace("https://", "http://", 1)
                    elif not url_attr.startswith("http://"):
                        enclosure.attrib["url"] = "http://" + url_attr
                    else:
                        enclosure.attrib["url"] = url_attr
            else:
                # 3️⃣ fallback: jen přidej http, pokud chybí
                if url_attr.startswith("https://"):
                    enclosure.attrib["url"] = url_attr.replace("https://", "http://", 1)
                elif not url_attr.startswith("http://"):
                    enclosure.attrib["url"] = "http://" + url_attr
                else:
                    enclosure.attrib["url"] = url_attr

    # 💾 Ulož výstupní XML
    output_path = os.path.join(OUTPUT_DIR, filename)
    ET.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"✅ Uloženo: {output_path}")
