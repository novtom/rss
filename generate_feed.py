import os
import base64
import requests
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse

# ===== Namespaces (zaregistrujeme, ať se hezky zapisují prefixy) =====
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
MEDIA_NS  = "http://search.yahoo.com/mrss/"
ATOM_NS   = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("media",  MEDIA_NS)
ET.register_namespace("atom",   ATOM_NS)

# ===== Nastavení =====
OUTPUT_DIR = "feeds"
MAX_ITEMS  = 30   # omezíme feed kvůli rychlosti LMS

podcasts = {
    "pro-a-proti.xml":     "https://api.mujrozhlas.cz/rss/podcast/0bc5da25-f081-33b6-94a3-3181435cc0a0.rss",
    "nazory-argumenty.xml":"https://api.mujrozhlas.cz/rss/podcast/f4133d64-ccb2-30e7-a70f-23e9c54d8e76.rss",
    "vinohradska12.xml":   "https://api.mujrozhlas.cz/rss/podcast/ee6095c0-33ac-3526-b8bf-df233af38211.rss",
    "Interview-plus.xml":  "https://api.mujrozhlas.cz/rss/podcast/1235fcbc-baa9-3656-9488-857fca2eb987.rss",
    "Osobnost-plus.xml":   "https://api.mujrozhlas.cz/rss/podcast/ad21758a-b517-328e-9bb0-2a2e2819f0b5.rss",
    "Podcasty-HN.xml":     "https://www.spreaker.com/show/4194705/episodes/feed",
    "Kecy-politika.xml":   "https://anchor.fm/s/99c6e0b4/podcast/rss",
    "Chyba-systemu.xml":   "https://api.mujrozhlas.cz/rss/podcast/47833fff-1845-3b97-b263-54fe2c4026b7.rss",
    "Ceska-satira.xml":    "https://api.mujrozhlas.cz/rss/podcast/4c2d5141-ad8d-3e73-b041-45170e6e1255.rss",
    "Vojta-zizka.xml":     "https://anchor.fm/s/763bc3a8/podcast/rss",
    "Mezi-rentiery.xml":   "https://audioboom.com/channels/5096524.rss",
    "Brain-we-are.xml":    "https://anchor.fm/s/7330de0/podcast/rss",
    "Fantastic-future.xml":"https://anchor.fm/s/102799d7c/podcast/rss",
    "5-59.xml":            "https://feeds.transistor.fm/5-59",
    "xtb.xml":             "https://anchor.fm/s/3de2cbdc/podcast/rss",
    "kilometry.xml":       "https://api.mujrozhlas.cz/rss/podcast/b2b82381-216d-310e-aeef-d46cd919d15d.rss",
    "ruz_vor.xml":         "https://anchor.fm/s/f5e22098/podcast/rss",
}

# ---------- Pomocné funkce ----------

def normalize_enclosure_url(raw: str) -> str:
    """Rozbalí přesměrování/encoding, dekóduje mujRozhlas a nutně přepíše na http:// (kvůli LMS)."""
    if not raw:
        return raw
    url = raw.strip()

    # Podtrac pryč
    url = url.replace("https://dts.podtrac.com/redirect.mp3/", "")
    url = url.replace("http://dts.podtrac.com/redirect.mp3/", "")

    # Rozbal percent-encoding (…https%3A%2F%2F…)
    if "%2F" in url or "%3A%2F%2F" in url:
        try:
            url = unquote(url)
        except Exception:
            pass

    # Anchor/Spotify styl: “…/http(s)://…mp3” – vezmi poslední http(s)://
    last_http = max(url.rfind("https://"), url.rfind("http://"))
    if last_http > 0:
        tail = url[last_http:]
        if ".mp3" in tail:
            url = tail

    # mujRozhlas aod/<base64>.mp3 → dekódovat
    try:
        p = urlparse(url)
        if "aod" in (p.path or "") and p.path.endswith(".mp3"):
            b64 = p.path.rsplit("/", 1)[-1].replace(".mp3", "")
            url = base64.urlsafe_b64decode(b64 + "==").decode("utf-8")
    except Exception:
        pass

    # Doplnit schéma a přepsat na http
    if url.startswith("https://"):
        url = "http://" + url[len("https://"):]
    elif not url.startswith("http://"):
        url = "http://" + url.lstrip("/")

    return url

def channel_image_url(channel) -> str | None:
    it = channel.find(f"{{{ITUNES_NS}}}image")
    if it is not None and it.get("href"):
        return it.get("href").strip()
    img = channel.find("image")
    if img is not None:
        u = img.find("url")
        if u is not None and (u.text or "").strip():
            return u.text.strip()
    return None

def ensure_item_artwork(item, fallback_url: str | None):
    """Doplní artwork (itunes:image + media:thumbnail), když chybí."""
    has_itunes = item.find(f"{{{ITUNES_NS}}}image")
    has_media  = item.find(f"{{{MEDIA_NS}}}thumbnail")
    if (has_itunes is None or not has_itunes.get("href")) and (has_media is None or not has_media.get("url")):
        if not fallback_url:
            return
        if has_itunes is None:
            has_itunes = ET.SubElement(item, f"{{{ITUNES_NS}}}image")
        has_itunes.set("href", fallback_url)
        if has_media is None:
            has_media = ET.SubElement(item, f"{{{MEDIA_NS}}}thumbnail")
        has_media.set("url", fallback_url)

def ensure_itunes_title(item):
    """Pro některé klienty doplníme itunes:title = <title>, pokud chybí."""
    el = item.find(f"{{{ITUNES_NS}}}title")
    if el is None:
        title_text = (item.findtext("title") or "").strip()
        ET.SubElement(item, f"{{{ITUNES_NS}}}title").text = title_text

# ---------- Hlavní zpracování jednoho feedu ----------

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
        for s in root.findall("script"):
            root.remove(s)
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

    # Omez počet položek
    items = channel.findall("item")
    if len(items) > MAX_ITEMS:
        for it in items[MAX_ITEMS:]:
            channel.remove(it)
        items = channel.findall("item")

    # Uprav link kanálu na GitHub Pages
    gh_url = f"https://novtom.github.io/rss/feeds/{filename}"
    link_el = channel.find("link")
    if link_el is not None:
        link_el.text = gh_url
    else:
        ET.SubElement(channel, "link").text = gh_url

    # Popis, pokud chybí
    if channel.find("description") is None:
        ET.SubElement(channel, "description").text = "RSS feed agregovaný a normalizovaný pro LMS."

    # Obrázek kanálu jako fallback pro epizody
    ch_img = channel_image_url(channel)

    # Projdi epizody
    for item in channel.findall("item"):
        enc = item.find("enclosure")
        if enc is not None and "url" in enc.attrib:
            enc.attrib["url"] = normalize_enclosure_url(enc.attrib["url"])
        ensure_itunes_title(item)
        ensure_item_artwork(item, ch_img)

    # Ulož
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, filename)
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    print(f"✅ Uloženo: {out}")

# ---------- Entrypoint ----------

def main():
    for filename, url in podcasts.items():
        process_feed(filename, url)

if __name__ == "__main__":
    main()
