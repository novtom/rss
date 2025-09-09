#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import base64
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote, quote

# ===== Namespaces =====
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
MEDIA_NS  = "http://search.yahoo.com/mrss/"
ATOM_NS   = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("media", MEDIA_NS)
ET.register_namespace("atom", ATOM_NS)

# ===== Nastavení =====
OUTPUT_DIR   = "feeds"
MAX_ITEMS    = 30
# Worker jede přes HTTP (LMS má problém s HTTPS přímo k CDN)
WORKER_RELAY = "http://podcast-relay.novtom.workers.dev/?u="

# Hosty, které typicky vyžadují HTTPS a/nebo dělají problémy s LMS
BLOCKED_HOST_PARTS = (
    "cloudfront.net",
    "media.transistor.fm",
    "transistor.fm",
    "megaphone.fm",
    "audioboom.com",
    "spotify.com",
    "spotifycdn",
    "anchor.fm",
    "spreaker.com",
)

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
    "xtb.xml": "https://anchor.fm/s/3de2cbdc/podcast/rss",
    "kilometry.xml": "https://api.mujrozhlas.cz/rss/podcast/b2b82381-216d-310e-aeef-d46cd919d15d.rss",
    "ruz_vor.xml": "https://anchor.fm/s/f5e22098/podcast/rss",
    "5-59.xml": "https://fetchrss.com/feed/aL_WevG8jIyCaL_WTqjkfiAi.rss",
}

# ===== Pomocné funkce =====

def clean_enclosure_url(raw: str) -> str | None:
    """Vrátí čisté přehratelné URL:
       - odstraní Podtrac,
       - rozbalí percent-encoding,
       - vytáhne „URL v URL“ (Anchor/Spotify),
       - dekóduje mujRozhlas AOD base64,
       - doplní schéma.
    """
    if not raw:
        return None
    url = raw.strip()

    # Podtrac pryč
    url = url.replace("https://dts.podtrac.com/redirect.mp3/", "")
    url = url.replace("http://dts.podtrac.com/redirect.mp3/", "")

    # Rozbal %xx
    try:
        url = unquote(url)
    except Exception:
        pass

    # „URL v URL“ – vezmi poslední http(s)://
    last_http = max(url.rfind("https://"), url.rfind("http://"))
    if last_http > 0:
        candidate = url[last_http:]
        if ".mp3" in candidate:
            url = candidate

    # mujRozhlas AOD base64 → skutečné URL
    try:
        p = urlparse(url)
        if "aod" in p.path and p.path.endswith(".mp3"):
            b64name = p.path.rsplit("/", 1)[-1].replace(".mp3", "")
            decoded = base64.urlsafe_b64decode(b64name + "==").decode("utf-8")
            url = decoded
    except Exception:
        pass

    # Doplň schéma
    if not url.startswith(("http://", "https://")):
        url = "http://" + url.lstrip("/")

    return url

def wrap_with_worker(url: str) -> str:
    """Obalí zdrojovou URL přes Cloudflare Worker (HTTP), LMS pak hraje spolehlivě."""
    # Encode param, ale ponech běžné delimiter znaky
    return f"{WORKER_RELAY}{quote(url, safe=':/?&=%')}"

def needs_worker(url: str) -> bool:
    """Rozhodni, zda enclosure obalit přes Worker (HTTPS nebo „problem host“)."""
    if url.startswith("https://"):
        return True
    host = (urlparse(url).hostname or "").lower()
    return any(part in host for part in BLOCKED_HOST_PARTS)

def get_channel_image(channel) -> str | None:
    it = channel.find(f"{{{ITUNES_NS}}}image")
    if it is not None and it.get("href"):
        return it.get("href").strip()
    img = channel.find("image")
    if img is not None:
        u = img.find("url")
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
        if (mc.get("medium") == "image") and mc.get("url"):
            return mc.get("url").strip()
    return None

def ensure_item_artwork_and_title(item, channel_img_url: str | None):
    # itunes:title – některé klienty to potřebují pro zobrazení názvu při přehrávání
    if item.find(f"{{{ITUNES_NS}}}title") is None:
        it_t = ET.SubElement(item, f"{{{ITUNES_NS}}}title")
        it_t.text = (item.findtext("title") or "").strip()

    # Dlaždice (itunes:image + media:thumbnail)
    img = get_item_image(item) or channel_img_url
    if not img:
        return
    it_img = item.find(f"{{{ITUNES_NS}}}image")
    if it_img is None:
        it_img = ET.SubElement(item, f"{{{ITUNES_NS}}}image")
    it_img.set("href", img)

    mt = item.find(f"{{{MEDIA_NS}}}thumbnail")
    if mt is None:
        mt = ET.SubElement(item, f"{{{MEDIA_NS}}}thumbnail")
    mt.set("url", img)

# ===== Hlavní zpracování jednoho feedu =====

def process_feed(filename: str, src_url: str):
    print(f"→ Zpracovávám {filename}")

    try:
        r = requests.get(src_url, timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Chyba stahování {src_url}: {e}")
        return

    try:
        root = ET.fromstring(r.content)
        # případné <script/> ven
        for script_tag in root.findall("script"):
            root.remove(script_tag)
    except ET.ParseError as e:
        print(f"❌ Chyba parsování XML z {src_url}: {e}")
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
        for it in items[MAX_ITEMS:]:
            channel.remove(it)
        items = channel.findall("item")

    # Link kanálu na GitHub Pages (informativní)
    gh_link = f"https://novtom.github.io/rss/feeds/{filename}"
    ch_link = channel.find("link")
    if ch_link is not None:
        ch_link.text = gh_link
    else:
        ET.SubElement(channel, "link").text = gh_link

    # Popis kanálu, pokud chybí
    if channel.find("description") is None:
        ET.SubElement(channel, "description").text = "RSS feed agregovaný a normalizovaný pro LMS."

    # Fallback artwork kanálu
    channel_img = get_channel_image(channel)

    # Přepočítej enclosure a doplň metadata u položek
    for item in items:
        enc = item.find("enclosure")
        if enc is not None and enc.get("url"):
            cleaned = clean_enclosure_url(enc.get("url"))
            if cleaned:
                enc.set("url", wrap_with_worker(cleaned) if needs_worker(cleaned) else cleaned)

        ensure_item_artwork_and_title(item, channel_img)

    # Ulož
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, filename)
    ET.ElementTree(root).write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"✅ Uloženo: {out_path}")

# ===== main =====

def main():
    for fname, src in podcasts.items():
        process_feed(fname, src)

if __name__ == "__main__":
    main()
