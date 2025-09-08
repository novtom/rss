import os
import requests
import xml.etree.ElementTree as ET
import base64
from urllib.parse import urlparse, unquote

# ===== Nastavení =====
OUTPUT_DIR = "feeds"
MAX_ITEMS = 30  # kolik epizod na feed

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

# ===== XML namespaces =====
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
MEDIA_NS = "http://search.yahoo.com/mrss/"
ATOM_NS = "http://www.w3.org/2005/Atom"

ET.register_namespace('itunes', ITUNES_NS)
ET.register_namespace('media', MEDIA_NS)
ET.register_namespace('atom', ATOM_NS)

def normalize_enclosure_url(raw: str) -> str:
    """Zruší podtrac, rozbalí percent-encoding, dekóduje mujRozhlas aod,
    a nastaví http/https podle hostitele (LMS-kompatibilní)."""
    if not raw:
        return raw
    url = raw.strip()

    # 1) zruš podtrac redirect
    url = url.replace("https://dts.podtrac.com/redirect.mp3/", "")
    url = url.replace("http://dts.podtrac.com/redirect.mp3/", "")

    # 2) rozbal percent-encoding (např. .../https%3A%2F%2F...)
    if "%3A%2F%2F" in url or "%2F" in url:
        try:
            url = unquote(url)
        except Exception:
            pass

    # 3) mujRozhlas „aod“: Base64 -> skutečná URL
    try:
        p = urlparse(url)
        if "aod" in p.path and p.path.endswith(".mp3"):
            b64name = p.path.rsplit("/", 1)[-1].replace(".mp3", "")
            decoded = base64.urlsafe_b64decode(b64name + "==").decode("utf-8")
            url = decoded
    except Exception:
        pass

    # 4) schema fallback
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    # 5) host-based rozhodnutí
    host = (urlparse(url).hostname or "").lower()

    # – mujRozhlas/croaod preferuje HTTP (kvůli LMS)
    if ("croaod.cz" in host) or ("rozhlas.cz" in host):
        if url.startswith("https://"):
            url = "http://" + url[len("https://"):]
    else:
        # – CDN/platformy necháme HTTPS
        force_https_hosts = (
            "cloudfront.net", "spotifycdn", "spotify.com",
            "anchor.fm", "spreaker.com", "transistor.fm",
            "megaphone.fm", "audioboom.com"
        )
        if any(h in host for h in force_https_hosts) and url.startswith("http://"):
            url = "https://" + url[len("http://"):]
    return url

def get_channel_image(channel) -> str | None:
    # itunes:image @href
    ch_it = channel.find(f"{{{ITUNES_NS}}}image")
    if ch_it is not None and ch_it.get("href"):
        return ch_it.get("href").strip()
    # <image><url>
    ch_img = channel.find("image")
    if ch_img is not None:
        u = ch_img.find("url")
        if u is not None and (u.text or "").strip():
            return u.text.strip()
    return None

def get_item_image(item) -> str | None:
    # epizodový itunes:image
    it = item.find(f"{{{ITUNES_NS}}}image")
    if it is not None and it.get("href"):
        return it.get("href").strip()
    # media:thumbnail
    mt = item.find(f"{{{MEDIA_NS}}}thumbnail")
    if mt is not None and mt.get("url"):
        return mt.get("url").strip()
    # media:content jako obrázek
    for mc in item.findall(f"{{{MEDIA_NS}}}content"):
        if (mc.get("medium") == "image") and mc.get("url"):
            return mc.get("url").strip()
    return None

def ensure_item_artwork(item, fallback_url: str | None):
    """Doplní itunes:image a media:thumbnail, pokud chybí."""
    img = get_item_image(item) or fallback_url
    if not img:
        return

    it = item.find(f"{{{ITUNES_NS}}}image")
    if it is None:
        it = ET.SubElement(item, f"{{{ITUNES_NS}}}image")
    it.set("href", img)

    mt = item.find(f"{{{MEDIA_NS}}}thumbnail")
    if mt is None:
        mt = ET.SubElement(item, f"{{{MEDIA_NS}}}thumbnail")
    mt.set("url", img)

def process_feed(filename: str, url: str):
    print(f"→ Zpracovávám {filename}")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Chyba stahování {url}: {e}")
        return

    try:
        root = ET.fromstring(r.content)
        # odstraň <script/> pokud by tam bylo
        for script_tag in root.findall("script"):
            root.remove(script_tag)
    except ET.ParseError as e:
        print(f"❌ Chyba parsování XML z {url}: {e}")
        return

    if root.tag != "rss":
        print(f"❌ Kořenový element není <rss> v {filename}")
        return

    channel = root.find("channel")
    if channel is None:
        print(f"❌ Nenalezen <channel> v {filename}")
        return

    # Omez počet epizod
    items = channel.findall("item")
    if len(items) > MAX_ITEMS:
        for item in items[MAX_ITEMS:]:
            channel.remove(item)
        items = channel.findall("item")  # refetch

    # Uprav <link> kanálu na GitHub Pages
    link = channel.find("link")
    gh_url = f"https://novtom.github.io/rss/feeds/{filename}"
    if link is not None:
        link.text = gh_url
    else:
        ET.SubElement(channel, "link").text = gh_url

    # Přidej <description> pokud chybí
    if channel.find("description") is None:
        ET.SubElement(channel, "description").text = "RSS feed agregovaný a normalizovaný pro LMS."

    # Zjisti obrázek kanálu (fallback pro epizody)
    channel_img_url = get_channel_image(channel)

  # 🔧 Úprava <enclosure> URL – rozbalit, očistit, převést na http
for item in channel.findall("item"):
    enclosure = item.find("enclosure")
    if enclosure is None or "url" not in enclosure.attrib:
        continue

    url_attr = enclosure.attrib["url"]

    # 1) Rozbal percent-encoding (…https%3A%2F%2F…)
    try:
        from urllib.parse import unquote, urlparse
        url_attr = unquote(url_attr)
    except Exception:
        pass

    # 2) Z Podtrac odstraň redirect prefix (ať zůstane čisté MP3)
    for pref in ("https://dts.podtrac.com/redirect.mp3/",
                 "http://dts.podtrac.com/redirect.mp3/"):
        if url_attr.startswith(pref):
            url_attr = url_attr[len(pref):]

    # 3) Anchor/Spotify: enclosure bývá "…/http(s)://cloudfront…mp3"
    #    – vezmeme POSLEDNÍ výskyt http(s):// a zbytek je skutečný stream
    last_http = max(url_attr.rfind("https://"), url_attr.rfind("http://"))
    if last_http > 0:
        candidate = url_attr[last_http:]
        # Pokud candidate vypadá smysluplně (končí .mp3 nebo má .mp3 query), bereme ho
        if ".mp3" in candidate:
            url_attr = candidate

    # 4) mujRozhlas base64 (…/aod/<base64>.mp3) → dekódovat na skutečný URL
    try:
        parsed = urlparse(url_attr)
        if "aod" in parsed.path and parsed.path.endswith(".mp3"):
            import base64
            b64name = parsed.path.split("/")[-1].replace(".mp3", "")
            decoded = base64.urlsafe_b64decode(b64name + "==").decode("utf-8")
            url_attr = decoded
    except Exception:
        # když dekódování selže, necháme původní url_attr
        pass

    # 5) Donutit http (LMS neumí https). Když schéma chybí, doplníme http://
    if url_attr.startswith("https://"):
        url_attr = "http://" + url_attr[len("https://"):]
    elif not url_attr.startswith("http://"):
        url_attr = "http://" + url_attr.lstrip("/")

    # 6) Zápis zpět
    enclosure.set("url", url_attr)

    # 7) (volitelné) Propagovat název epizody i jako itunes:title – LMS to někdy používá
    it_title = item.find(f"{{{ITUNES_NS}}}title") if 'ITUNES_NS' in globals() else None
    if it_title is None:
        # vytvoř itunes:title jen pokud ještě není
        try:
            from xml.etree.ElementTree import SubElement
            SubElement(item, f"{{{ITUNES_NS}}}title").text = (item.findtext("title") or "").strip()
        except Exception:
            pass

    # 8) Obrázek epizody (dlaždice): pokud chybí, použij obrázek kanálu
    if channel_img_url:
        it_img = item.find(f"{{{ITUNES_NS}}}image") if 'ITUNES_NS' in globals() else None
        md_thumb = item.find(f"{{{MEDIA_NS}}}thumbnail") if 'MEDIA_NS' in globals() else None
        if (it_img is None or not it_img.get("href")) and (md_thumb is None or not md_thumb.get("url")):
            try:
                from xml.etree.ElementTree import SubElement
                # itunes:image
                SubElement(item, f"{{{ITUNES_NS}}}image", {"href": channel_img_url})
                # media:thumbnail
                SubElement(item, f"{{{MEDIA_NS}}}thumbnail", {"url": channel_img_url})
            except Exception:
                pass

    # Ulož výstup
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, filename)
    ET.ElementTree(root).write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"✅ Uloženo: {output_path}")

def main():
    for filename, url in podcasts.items():
        process_feed(filename, url)

if __name__ == "__main__":
    main()
