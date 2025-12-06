import requests
from bs4 import BeautifulSoup
import json
import os
import time

API_BASE = os.getenv("API_BASE_URL", "").rstrip("/")
MAX_PAGES = int(os.getenv("MAX_PAGES", 20))
STORIES_PER_RUN = 5
START_PAGE = 3

DOMAIN = "https://nettruyen0209.com"
LIST_URL = DOMAIN + "/danh-sach-truyen/{page}/?sort=last_update&status=0"
POSTED_FILE = "posted.json"


# ==============================
# Load/save
# ==============================
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []
    return json.load(open(POSTED_FILE, "r", encoding="utf-8"))


def save_posted(lst):
    json.dump(lst, open(POSTED_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


# ==============================
# Lấy danh sách truyện
# ==============================
def get_story_links():
    links = []

    print("=== 🔍 START SCANNING FOR STORIES ===")

    for page in range(START_PAGE, MAX_PAGES + 1):
        url = LIST_URL.format(page=page)
        print(f"\n📄 Checking page {page}: {url}")

        try:
            html = requests.get(url, timeout=10).text
        except:
            print("❌ Failed to load page")
            continue

        soup = BeautifulSoup(html, "html.parser")

        # FIX selector mới của nettruyen0209
        items = soup.select("div.item > a, div.item a.image")

        if not items:
            print("⚠ No more items → stop scan")
            break

        added = 0
        for a in items:
            link = a.get("href")
            if not link:
                continue
            if link.startswith("/"):
                link = DOMAIN + link
            if DOMAIN not in link:
                continue
            links.append(link)
            added += 1

        print(f"➕ Added {added} links from page {page}")
        time.sleep(0.2)

    print(f"\n🎉 TOTAL LINKS: {len(links)}")
    return links


# ==============================
# Scrap chapter images
# ==============================
def scrape_chapter_images(url):
    # FIX URL sai dạng "/manga/..."
    if url.startswith("/"):
        url = DOMAIN + url

    try:
        html = requests.get(url, timeout=10).text
    except:
        print("❌ Error loading chapter:", url)
        return []

    soup = BeautifulSoup(html, "html.parser")

    imgs = []
    for img in soup.select(".page-chapter img"):
        src = img.get("data-src") or img.get("src")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        imgs.append(src)

    return imgs


# ==============================
# Scrap full story
# ==============================
def scrape_story(url):
    print("\n=== 📘 SCRAPING STORY ===")
    print(url)

    try:
        html = requests.get(url, timeout=10).text
    except:
        print("❌ Cannot load story URL")
        return None

    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one(".title-detail")
    title = title.text.strip() if title else "No Title"

    cover_node = soup.select_one(".detail-info img")
    cover = cover_node.get("src") if cover_node else ""

    des_node = soup.select_one(".detail-content p")
    description = des_node.text.strip() if des_node else ""

    chapters = []
    ch_nodes = soup.select(".list-chapter li a")

    for c in ch_nodes[::-1]:  # ASC order
        ch_name = c.text.strip()
        ch_url = c.get("href")

        if not ch_url:
            continue
        if ch_url.startswith("/"):
            ch_url = DOMAIN + ch_url

        chapter_imgs = scrape_chapter_images(ch_url)

        chapters.append({
            "chapter": ch_name,
            "images": chapter_imgs
        })

        time.sleep(0.3)

    return {
        "name": title,
        "cover": cover,
        "description": description,
        "chapters": chapters
    }


# ==============================
# Upload API
# ==============================
def upload_story(data):
    if not API_BASE:
        print("❌ API_BASE_URL missing!")
        return False

    try:
        res = requests.post(f"{API_BASE}/api/stories/create", json=data)
        print(f"📤 API Response: {res.status_code} {res.text}")
        return res.status_code == 200
    except Exception as e:
        print("❌ API upload error:", e)
        return False


# ==============================
# MAIN
# ==============================
def main():
    posted = load_posted()
    all_links = get_story_links()

    new_links = [l for l in all_links if l not in posted]

    if not new_links:
        print("🎉 No new stories left.")
        return

    print(f"\n📌 Stories remaining: {len(new_links)}")
    print(f"🚀 Will upload next {STORIES_PER_RUN} stories")

    uploaded = 0

    for url in new_links:
        if uploaded >= STORIES_PER_RUN:
            break

        data = scrape_story(url)
        if not data:
            continue

        if upload_story(data):
            posted.append(url)
            uploaded += 1
            save_posted(posted)
            print(f"✅ Uploaded {uploaded}/{STORIES_PER_RUN}")

        time.sleep(1)

    print("\n🎯 DONE.")


if __name__ == "__main__":
    main()
