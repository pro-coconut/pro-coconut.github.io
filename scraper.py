#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Scraper full: nettruyen0209.com -> gọi API (create/check story, add chapter)
Cấu hình qua ENV:
  API_BASE_URL = "https://manga-api-gr26.onrender.com"  - (bắt buộc) ví dụ: https://manga-api-abc.onrender.com
  API_KEY        - (tùy chọn) Bearer token nếu API yêu cầu auth
  MAX_LISTING_PAGES - (tùy chọn) số trang listing sẽ quét (mặc định 5)
  MAX_STORIES       - (tùy chọn) giới hạn tổng truyện cho test (None = vô hạn)
  DELAY             - (tùy chọn) delay giữa request (giây) mặc định 1.5
"""

import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import sys

# ========== CẤU HÌNH ==========
BASE_SITE = "https://nettruyen0209.com"
API_BASE = os.environ.get("API_BASE_URL") or os.environ.get("API_BASE") or ""
API_KEY = os.environ.get("API_KEY")  # optional
MAX_LISTING_PAGES = int(os.environ.get("MAX_LISTING_PAGES", "5"))
MAX_STORIES = os.environ.get("MAX_STORIES")  # optional limit for testing
DELAY = float(os.environ.get("DELAY", "1.5"))

if not API_BASE:
    print("ERROR: Bạn cần set biến môi trường API_BASE_URL (ví dụ https://manga-api-xxx.onrender.com).")
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"
}
if API_KEY:
    HEADERS["Authorization"] = f"Bearer {API_KEY}"

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ========== HÀM HỖ TRỢ HTTP ==========
def safe_get(url, timeout=20):
    try:
        r = SESSION.get(url, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"[GET ERROR] {url} -> {e}")
        return None

def api_post(path, payload):
    url = API_BASE.rstrip("/") + path
    try:
        r = SESSION.post(url, json=payload, timeout=30)
        r.raise_for_status()
        try:
            return r.json()
        except:
            return {"status": "ok", "raw_text": r.text}
    except Exception as e:
        print(f"[API POST ERROR] {url} -> {e}")
        return None

def api_get(path):
    url = API_BASE.rstrip("/") + path
    try:
        r = SESSION.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API GET ERROR] {url} -> {e}")
        return None

# ========== 1) GATHER MANGA LINKS (từng bộ một) ==========
def gather_manga_links(max_pages=MAX_LISTING_PAGES, max_stories=None):
    """
    Quét các trang listing để lấy link truyện (link có '/manga/')
    Trả về list các link (unique) theo thứ tự tìm thấy.
    """
    found = []
    seen = set()

    # seeds (trang chủ + trang truyện)
    seeds = [BASE_SITE, urljoin(BASE_SITE, "/truyen-tranh")]

    # quét seed đầu tiên
    for seed in seeds:
        r = safe_get(seed)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/manga/" in href:
                full = urljoin(BASE_SITE, href)
                if full not in seen:
                    seen.add(full)
                    found.append(full)
                    print("Found:", full)
                    if max_stories and len(found) >= int(max_stories):
                        return found

    # quét theo các page variants
    for page in range(1, max_pages + 1):
        # thử 2 kiểu page query thông dụng
        for variant in [f"{BASE_SITE}/truyen-tranh?page={page}", f"{BASE_SITE}/truyen-tranh/page/{page}"]:
            print("Scanning listing:", variant)
            r = safe_get(variant)
            if not r:
                time.sleep(DELAY)
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            added = 0
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/manga/" in href:
                    full = urljoin(BASE_SITE, href)
                    if full not in seen:
                        seen.add(full)
                        found.append(full)
                        added += 1
                        print("  →", full)
                        if max_stories and len(found) >= int(max_stories):
                            return found
            print(f"  Added {added} links from {variant}")
            time.sleep(DELAY)
    print("Total links found:", len(found))
    return found

# ========== 2) PARSE STORY PAGE (lấy info + list chapter links) ==========
def parse_story_page(story_url):
    """
    Trả về dict:
    {
      title, id_slug, thumbnail, description, chapters: [{name, url}, ...]
    }
    """
    r = safe_get(story_url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    # Title
    title_elem = soup.select_one("h1.title-detail") or soup.select_one("h1")
    title = title_elem.get_text(strip=True) if title_elem else "No title"

    # slug id đơn giản
    id_slug = re.sub(r'[^a-z0-9]', '', title.lower())

    # thumbnail
    thumb = ""
    img_elem = soup.select_one(".col-image img, .book img, img[itemprop='image'], .thumb img")
    if img_elem:
        thumb = img_elem.get("src") or img_elem.get("data-src") or ""

    # description
    desc = ""
    desc_elem = soup.select_one(".detail-content, .summary, .desc, #tab-summary")
    if desc_elem:
        desc = desc_elem.get_text(strip=True)

    # chapter list - nhiều selector để bền
    chap_selectors = [
        ".list-chapter li a",
        "ul.row-content-chapter li a",
        ".chapter-list a",
        ".chapter_list a",
        ".chapters a",
        "a[href*='/manga/'][href*='chapter']"
    ]

    chap_links = []
    for sel in chap_selectors:
        elems = soup.select(sel)
        if elems:
            for a in elems:
                href = a.get("href")
                name = a.get_text(strip=True)
                if href and name:
                    full = urljoin(BASE_SITE, href)
                    chap_links.append({"name": name, "url": full})
            if chap_links:
                break

    # fallback: scan all anchors for 'chapter' in href
    if not chap_links:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "chapter" in href.lower() or re.search(r'/chapter[-_/]?\d+', href, re.I):
                name = a.get_text(strip=True) or href.split("/")[-1]
                chap_links.append({"name": name, "url": urljoin(BASE_SITE, href)})

    # dedupe preserve order then reverse to ensure chap1 -> chapN
    seen = set()
    cleaned = []
    for c in chap_links:
        if c["url"] not in seen:
            seen.add(c["url"])
            cleaned.append(c)
    cleaned.reverse()
    print(f"Parsed story: {title} - {len(cleaned)} chapters")
    return {
        "title": title,
        "id_slug": id_slug,
        "thumbnail": thumb,
        "description": desc,
        "chapters": cleaned
    }

# ========== 3) PARSE CHAPTER IMAGES ==========
def parse_chapter_images(chap_url):
    r = safe_get(chap_url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    selectors = [
        ".reading-detail img",
        ".chapter-content img",
        ".page-chapter img",
        ".container-chapter-reader img",
        "img"
    ]
    imgs = []
    for sel in selectors:
        elems = soup.select(sel)
        if elems:
            for img in elems:
                src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
                if src and src.startswith("http"):
                    imgs.append(src)
            if imgs:
                break
    # filter icons
    imgs = [u for u in imgs if not any(x in u for x in ["/logo", "favicon", "icons", "icon"])]
    print(f"    Images found: {len(imgs)}")
    return imgs

# ========== 4) GỌI API: check/create story, add chapter ==========
def check_story_api(name):
    payload = {"name": name}
    res = api_post("/api/stories/check", payload)
    if res is None:
        return None
    # res expected: {exists: bool, storyId: ..., chapters: [...]}
    return res

def create_story_api(name, cover, description):
    payload = {"name": name, "cover": cover, "description": description}
    res = api_post("/api/stories/create", payload)
    return res

def add_chapter_api(story_id, chapter_name, images):
    payload = {"storyId": story_id, "chapter": chapter_name, "images": images}
    res = api_post("/api/stories/add-chapter", payload)
    return res

# ========== 5) XỬ LÝ 1 TRUYỆN ==========
def process_story(link):
    print("\n=== Processing story:", link)
    parsed = parse_story_page(link)
    if not parsed:
        print("  ! Parse failed, skip.")
        return

    # 1) kiểm tra story trên API
    chk = check_story_api(parsed["title"])
    if chk is None:
        print("  ! API check failed, skip story.")
        return

    if not chk.get("exists"):
        # create
        print("  → Story not exists on API, creating...")
        res = create_story_api(parsed["title"], parsed["thumbnail"], parsed["description"])
        if not res:
            print("  ! Create story API failed.")
            return
        story_id = res.get("storyId") or res.get("id")
        print("  → Created story id:", story_id)
        existing_ch_names = set()
    else:
        story_id = chk.get("storyId")
        existing_ch_names = set(chk.get("chapters", []) or [])
        print("  → Story exists id:", story_id, "existing chapters:", len(existing_ch_names))

    # 2) iterate chapters and add missing
    added = 0
    for chap in parsed["chapters"]:
        chap_name = chap["name"]
        if chap_name in existing_ch_names:
            print("   - Chapter already exists:", chap_name)
            continue
        print("   - New chapter:", chap_name, "-> fetch images")
        images = parse_chapter_images(chap["url"])
        if not images:
            print("     ! No images found, skipping chapter")
            continue
        res = add_chapter_api(story_id, chap_name, images)
        if res is None:
            print("     ! API add chapter failed")
            continue
        print("     ✓ Added chapter:", chap_name)
        added += 1
        time.sleep(DELAY)
    print(f"  => Done. Chapters added: {added}")

# ========== MAIN ==========
def main():
    print("=== Scraper Bot START ===")
    links = gather_manga_links(max_pages=MAX_LISTING_PAGES, max_stories=MAX_STORIES)
    print("Total stories to process:", len(links))
    for idx, link in enumerate(links, start=1):
        print(f"\n[{idx}/{len(links)}] {link}")
        try:
            process_story(link)
        except Exception as e:
            print("  ERROR processing:", e)
        # small delay between stories
        time.sleep(DELAY)
    print("=== Scraper Bot FINISHED ===")

if __name__ == "__main__":
    main()
