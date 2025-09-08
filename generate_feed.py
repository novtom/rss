import os
import requests
import xml.etree.ElementTree as ET
import base64
from urllib.parse import urlparse, unquote

# --- namespaces pro iTunes a Media RSS ---
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
MRSS_NS   = "http://search.yahoo.com/mrss/"
ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("media", MRSS_NS)

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
# Obrázek kanálu – použijeme ho jako fallback pro epizody
channel_img_url = None
ch_itunes_img = channel.find(f"{{{ITUNES_NS}}}image")
if ch_itunes_img is not None and ch_itunes_img.get("href"):
    channel_img_url = ch_itunes_img.get("href")
else:
    ch_img = channel.find("image")
    if ch_img is not None:
        ch_url = ch_img.find("url")
        if ch_url is not None and ch_url.text:
            channel_img_url = ch_url.text.strip()



# --- zjisti URL obrázku kanálu jako fallback pro epizody ---
channel_img_url = None

# <image><url>...</url></image>
img_tag = channel.find("image")
if img_tag is not None:
    url_tag = img_tag.find("url")
    if url_tag is not None and url_tag.text:
        channel_img_url = url_tag.text.strip()

# <itunes:image href="..."/>
if not channel_img_url:
    it_img = channel.find(f"{{{ITUNES_NS}}}image")
    if it_img is not None and it_img.get("href"):
        channel_img_url = it_img.get("href").strip()
    # 🔻 Omez počet epizod v RSS feedu
    items = channel.findall("item")
    max_items = 30  # změň podle potřeby (např. 200)
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
    # itunes:title – aby se při přehrávání zobrazil název epizody
    if item.find(f"{{{ITUNES_NS}}}title") is None:
        t = item.find("title")
        if t is not None and t.text:
            ET.SubElement(item, f"{{{ITUNES_NS}}}title").text = t.text

    # Obrázky epizody: vezmi per-item iTunes/MRSS; když chybí, spadni na obrázek kanálu
    has_itunes_img  = item.find(f"{{{ITUNES_NS}}}image") is not None
    has_media_thumb = item.find(f"{{{MRSS_NS}}}thumbnail") is not None
    if (not has_itunes_img or not has_media_thumb) and channel_img_url:
        if not has_itunes_img:
            ET.SubElement(item, f"{{{ITUNES_NS}}}image", {"href": channel_img_url})
        if not has_media_thumb:
            ET.SubElement(item, f"{{{MRSS_NS}}}thumbnail", {"url": channel_img_url})

    enclosure = item.find("enclosure")
    if enclosure is None or "url" not in enclosure.attrib:
        continue

    url_attr = enclosure.attrib["url"]

    # 1) Anchor/Spotify: cesta obsahuje percent-enkódované https://...mp3 za "/podcast/play/<id>/"
    extracted = None
    if "/podcast/play/" in url_attr and ("%3A%2F%2F" in url_attr or "%2F" in url_attr):
        try:
            # vezmi část za posledním "/" a rozbal ji (většinou je to celé enkódovaná cílová URL)
            # někdy je ale enkódované víc než poslední segment – proto zkus najít první výskyt 'http' v enkódované podobě
            pos = url_attr.find("https%3A%2F%2F")
            if pos == -1:
                pos = url_attr.find("http%3A%2F%2F")
            if pos != -1:
                encoded_tail = url_attr[pos:]
            else:
                encoded_tail = url_attr.rsplit("/", 1)[-1]

            u = unquote(encoded_tail)
            extracted = u
        except Exception:
            extracted = None

    final_url = extracted or url_attr

    # 2) Zahoď případný Podtrac redirect
    final_url = final_url.replace("https://dts.podtrac.com/redirect.mp3/", "")
    final_url = final_url.replace("http://dts.podtrac.com/redirect.mp3/", "")

    # 3) Preferuj http (kvůli LMS); když začíná na https, přepiš na http
    if final_url.startswith("https://"):
        final_url = "http://" + final_url[len("https://"):]
    elif not final_url.startswith(("http://", "https://")):
        # kdyby po unquote zůstal čistý host/Path bez schématu
        final_url = "http://" + final_url

    enclosure.set("url", final_url)
# --- doplň metadata epizody: itunes:title a obrázek pro epizodu ---
# itunes:title = stejné jako <title> (některé klienty to chtějí kvůli zobrazení)
title_tag = item.find("title")
if title_tag is not None and (title_tag.text or "").strip():
    # vytvoř jen pokud chybí
    if item.find(f"{{{ITUNES_NS}}}title") is None:
        it_title = ET.SubElement(item, f"{{{ITUNES_NS}}}title")
        it_title.text = title_tag.text.strip()

# obrázek epizody – jen když není; použijeme obrázek kanálu
if channel_img_url:
    has_itunes_image = item.find(f"{{{ITUNES_NS}}}image") is not None
    has_mrss_thumb   = item.find(f"{{{MRSS_NS}}}thumbnail") is not None
    if not (has_itunes_image or has_mrss_thumb):
        it_img = ET.SubElement(item, f"{{{ITUNES_NS}}}image")
        it_img.set("href", channel_img_url)
        thumb = ET.SubElement(item, f"{{{MRSS_NS}}}thumbnail")
        thumb.set("url", channel_img_url)
    # 💾 Ulož výstupní XML
    output_path = os.path.join(OUTPUT_DIR, filename)
    ET.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"✅ Uloženo: {output_path}")
