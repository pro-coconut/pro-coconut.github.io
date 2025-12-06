#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robust scraper with verbose logging, retries, timeouts, and safe failure.
Designed for GitHub Actions.
"""
import os
import json
import time
import traceback
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ----------------- Config -----------------
API_BASE = os.getenv("API_BASE_URL", "").rstrip("/")
MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))   # <- default small for testing
STORIES_PER_RUN = int(os.getenv("STORIES_PER_RUN", "3"))
START_PAGE = int(os.getenv("START_PAGE", "3"))
DOMAIN = "https://nettruyen0209.com"
LIST_URL = DOMAIN + "/danh-sach-truyen/{page}/?sort=last_update&status=0"
POSTED_FILE = "posted.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"
}

# ----------------- Session + Retry -----------------
session = requests.Session()
retry = Retry(total=3, backoff_factor=0.4, status_forcelist=(429, 500, 502, 503, 504))
session.mount("https://", HTTPAdapter(max_retries=retry))
session.mount("http://", HTTPAdapter(max_retries=retry))


# ----------------- Helpers -----------------
def log(msg):
    print(msg, flush=True)


def safe_get(url, timeout=10):
    try:
        r = session.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        log(f"[GET ERROR] {url} -> {e}")
        return None


def safe_post(url, json_payload, timeout=15):
    try:
        r = session.post(url, json=json_payload, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        log(f"[POST ERROR] {url} -> {e}")
        return None


# ----------------- File helpers -----------------
def ensure_posted_file():
    if not os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def load_posted():
    ensure_posted_file()
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_posted(lst):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)


# ----------------- Scraping functions -----------------
def get_story_links(limit):
    log("=== START: collect story links ===")
    links = []
    for page in range(START_PAGE, START_PAGE + MAX_PAGES):
        if len(links) >= limit:
            break
        url = LIST_URL.format(page=page)
        log(f"Scanning page {page}: {url}")
        r = safe_get(url)
        if not r:
            log(f"  - failed to fetch page {page}, skipping")
            time.sleep(0.5)
            continue
        soup = BeautifulSoup(r.text, "lxml")
        # selector tuned to your site
        items = soup.select("div.item figure a")
        if not items:
            log(f"  - no items found on page {page}, stop scanning pages")
            break
        for a in items:
            if len(links) >= limit:
                break
            href = a.get("href")
            if not href:
                continue
            if href.startswith("/"):
                href = DOMAIN + href
            # normalize
            if not href.startswith("http"):
                href = DOMAIN + href
            links.append(href)
        log(f"  + collected {len(items)} links (total {len(links)})")
        time.sleep(0.2)
    log(f"=== FINISH: collected {len(links)} links ===")
    return links


def scrape_chapter_images(chap_url):
    if chap_url.startswith("/"):
        chap_url = DOMAIN + chap_url
    r = safe_get(chap_url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = []
    # try multiple selectors
    selectors = [".page-chapter img", ".reading-detail img", ".chapter-content img", "img"]
    for sel in selectors:
        for img in soup.select(sel):
            src = img.get("data-src") or img.get("src") or img.get("data-original")
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            if src.startswith("/"):
                src = DOMAIN + src
            if src not in imgs:
                imgs.append(src)
        if imgs:
            break
    log(f"    -> images found: {len(imgs)}")
    return imgs


def scrape_story(url):
    log(f"\n=== SCRAPE STORY: {url} ===")
    r = safe_get(url)
    if not r:
        log("  ! cannot load story page")
        return None
    soup = BeautifulSoup(r.text, "lxml")
    title_el = soup.select_one(".title-detail") or soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else "No Title"
    cover_el = soup.select_one(".detail-info img") or soup.select_one(".col-image img")
    cover = cover_el.get("src") if cover_el else ""
    desc_el = soup.select_one(".detail-content p") or soup.select_one(".summary")
    description = desc_el.get_text(strip=True) if desc_el else ""
    # chapters list
    ch_nodes = soup.select(".list-chapter li a") or soup.select("ul.row-content-chapter li a") or soup.select(".chapter-list a")
    chapters = []
    # reverse to get chap1..chapN if site lists newest first
    ch_nodes = ch_nodes[::-1]
    for c in ch_nodes:
        name = c.get_text(strip=True)
        href = c.get("href")
        if not href:
            continue
        if href.startswith("/"):
            href = DOMAIN + href
        imgs = scrape_chapter_images(href)
        chapters.append({"chapter": name, "images": imgs})
        # small sleep to be polite
        time.sleep(0.12)
    log(f"  -> story '{title}' scraped with {len(chapters)} chapters")
    return {
        "name": title,
        "cover": cover,
        "description": description,
        "chapters": chapters
    }


# ----------------- API helpers -----------------
def upload_story(data):
    if not API_BASE:
        log("❌ ERROR: API_BASE_URL not set in secrets. Aborting upload.")
        return False
    url = API_BASE.rstrip("/") + "/api/stories/create"
    log(f"Uploading to API: {url} (chapters={len(data.get('chapters', []))})")
    r = safe_post(url, data)
    if not r:
        log("  -> upload failed (no response)")
        return False
    try:
        j = r.json()
        ok = j.get("success") is True
        log(f"  -> api returned success={ok} ; raw: {r.text}")
        return ok
    except Exception as e:
        log(f"  -> invalid json response: {e}")
        return False


# ----------------- Main -----------------
def main():
    start = time.time()
    try:
        log("=== BOT START ===")
        # quick env print
        log(f"ENV: API_BASE set? {'YES' if API_BASE else 'NO'}, MAX_PAGES={MAX_PAGES}, STORIES_PER_RUN={STORIES_PER_RUN}")
        ensure = ensure_posted_file if 'ensure_posted_file' in globals() else None
        # ensure posted file exists:
        if not os.path.exists(POSTED_FILE):
            save_posted([])

        posted = load_posted()
        # collect only needed links (limit = STORIES_PER_RUN * 2 for buffer)
        links = get_story_links(limit=STORIES_PER_RUN * 3)
        if not links:
            log("No links found → exit")
            return

        # remove already posted
        candidates = [l for l in links if l not in posted]
        log(f"Candidates for upload: {len(candidates)}")

        uploaded = 0
        for link in candidates:
            if uploaded >= STORIES_PER_RUN:
                break
            try:
                st = scrape_story(link)
                if not st:
                    continue
                # prepare payload (format kiểu 1)
                payload = {
                    "name": st["name"],
                    "cover": st["cover"],
                    "description": st["description"],
                    "chapters": st["chapters"]
                }
                ok = upload_story(payload)
                if ok:
                    posted.append(link)
                    save_posted(posted)
                    uploaded += 1
                else:
                    log("Upload not successful; skipping to next story")
                # small pause between stories
                time.sleep(0.5)
            except Exception:
                log("Exception while processing story:")
                traceback.print_exc()
        log(f"=== DONE: uploaded {uploaded} stories in {time.time()-start:.1f}s ===")
    except Exception:
        log("Fatal exception in main:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
