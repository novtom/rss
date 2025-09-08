import os
import base64
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote, quote

# ===== Namespaces (aby se pekně zapsaly itunes:/media:) =====
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
MEDIA_NS  = "http://search.yahoo.com/mrss/"
ATOM_NS   = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("media", MEDIA_NS)
ET.register_namespace("atom", ATOM_NS)

# ===== Nastavení =====
OUTPUT_DIR = "feeds"
MAX_ITEMS  = 30
RELAY_BASE = "https://podcast-relay.novtom.workers.dev/?u="

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

# ===== Pomocné funkce =====
def remove_podtrac(url: str) -> str:
    return (url
            .replace("https://dts.podtrac.com/redirect.mp3/", "")
            .replace("http://dts.podtrac.com/redirect.mp3/", ""))

def decode_mujrozhlas_aod(url: str) -> str:
    """
    Pokud je to mujRozhlas AOD tvar (.../aod/<base64>.mp3),
    vrátí dekódovanou URL, jinak vrátí původní.
    """
    try:
        p = urlparse(url)
        if "aod" in p.path and p.path.endswith(".mp3"):
            b64name = p.path.rsplit("/", 1)[-1].replace(".mp3", "")
            dec = base64.urlsafe_b64decode(b64name + "==").decode("utf-8")
            return dec
    except Exception:
        pass
    return url

def extract_last_http_segment(url: str) -> str:
    """
    Anchor/Spotify často dávají do enclosure něco jako:
    http://anchor.fm/.../https%3A%2F%2Fcloudfront...mp3
    → vezmeme POSLEDNÍ výskyt http(s):// a zbytek.
    """
    u = unquote(url)
    idx_https = u.rfind("https://")
    idx_http  = u.rfind("http://")
    idx = max(idx_https, idx_http)
    if idx > 0:
        candidate = u[idx:]
        if ".mp3" in candidate:
            return candidate
    return u

def normalize_enclosure(url: str) -> str:
    """
    1) rozbal percent-encoding
    2) sundej podtrac
    3) vytáhni skutečný http(s) segment (Anchor apod.)
    4) mujRozhlas aod decode
    5) routing: Rozhlas → http (bez relaye), ostatní → přes https + relay
    """
    if not url:
        return url

    # 1+2
    url = remove_podtrac(unquote(url))

    # 3
    url = extract_last_http_segment(url)

    # 4
    url = decode_mujrozhlas_aod(url)

    # 5 rozhodnutí podle hosta
    if not url.startswith(("http://", "https://")):
        url = "http://" + url.lstrip("/")

    host = (urlparse(url).hostname or "").lower()

    # Rozhlas (croaod/rozhlas) jede po staru na HTTP (LMS)
    if ("croaod.cz" in host) or ("rozhlas.cz" in host):
        # vynutit http
        if url.startswith("https://"):
            url = "http://" + url[len("https://"):]
        return url

    # Všechno ostatní → přepnout na https (kvůli originům) a poslat přes relay
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return RELAY_BASE + quote(url, safe="")

def get_channel_image(channel) -> str | None:
    it = channel.find(f"{{{ITUNES_NS}}}image")
    if it is not None and it.get("href"):
        return it.get("href").strip()
    ch_img = channel.find("image")
    if ch_img is not None:
        u = ch_img.find("url")
        if u is not None and (u.text or "").strip():
            return u.text.strip()
    return None

def get_item_image(item) -> str | None:
    it = item.find(f"{{{ITUNES_NS}}}image")
    if it is not None and it.get("href"):
        return it.get("href").strip()
    mt = item.find(f"{{{MEDIA_NS}}}thumbnail")
    if mt is not None and mt.get("url"):
        return mt.get("url").strip()
    for mc in item.findall(f"{{{MEDIA_NS}}}content"):
        if mc.get("medium") == "image" and mc.get("url"):
            return mc.get("url").strip()
    return None

def ensure_item_artwork(item, fallback_url: str | None):
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
        # kdyby náhodou přišlo <script/>, vyhodíme
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
        items = channel.findall("item")

    # Uprav <link> kanálu na GitHub Pages
    gh_url = f"https://novtom.github.io/rss/feeds/{filename}"
    link = channel.find("link")
    if link is not None:
        link.text = gh_url
    else:
        ET.SubElement(channel, "link").text = gh_url

    # Přidej <description> pokud chybí
    if channel.find("description") is None:
        ET.SubElement(channel, "description").text = "RSS feed agregovaný a normalizovaný pro LMS."

    # Fallback obrázek kanálu
    channel_img_url = get_channel_image(channel)

    # Enclosure + artwork pro každou epizodu
    for item in channel.findall("item"):
        enc = item.find("enclosure")
        if enc is not None and "url" in enc.attrib:
            raw_url = enc.attrib["url"]
            final_url = normalize_enclosure(raw_url)
            enc.set("url", final_url)

        # itunes:title (některé klienty ho berou)
        if item.find(f"{{{ITUNES_NS}}}title") is None:
            t = (item.findtext("title") or "").strip()
            if t:
                ET.SubElement(item, f"{{{ITUNES_NS}}}title").text = t

        # obrázek epizody (dlaždice)
        ensure_item_artwork(item, channel_img_url)

    # Ulož
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, filename)
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    print(f"✅ Uloženo: {out}")

def main():
    for filename, url in podcasts.items():
        process_feed(filename, url)

if __name__ == "__main__":
    main()
