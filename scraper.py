import os
import json
import time
import requests
from bs4 import BeautifulSoup

API_BASE_URL = os.getenv("API_BASE_URL")
START_PAGE = int(os.getenv("START_PAGE", 1))
STORIES_PER_RUN = int(os.getenv("STORIES_PER_RUN", 3))
MAX_PAGES = int(os.getenv("MAX_PAGES", 20))
BATCH_SIZE = 5

HEADERS = { "User-Agent": "Mozilla/5.0", "Accept": "*/*" }

# =====================================================
# STORIES STORAGE (REPLACES posted.json)
# =====================================================

STORIES_FILE = "stories.json"

def load_stories():
    if not os.path.exists(STORIES_FILE):
        return []
    with open(STORIES_FILE, "r", encoding="utf8") as f:
        return json.load(f)

def save_stories(data):
    with open(STORIES_FILE, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =====================================================
# UTILITIES
# =====================================================

def safe_get(url):
    for _ in range(5):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r
            time.sleep(2)
        except:
            time.sleep(2)
    return None

# =====================================================
# SCRAPE CHAPTER
# =====================================================

def scrape_chapter(url):
    r = safe_get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select("div.page-chapter > img")
    return [img.get("src") for img in imgs if img.get("src")]

# =====================================================
# SCRAPE STORY
# =====================================================

def scrape_story(story_url):
    r = safe_get(story_url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "lxml")

    title_el = soup.select_one("h1.title-detail")
    if not title_el:
        print("Không tìm thấy title → trang lỗi?")
        return None
    title = title_el.text.strip()

    chapter_links = [a["href"] for a in soup.select("ul.list-chapter a") if a.get("href")]
    chapter_links = chapter_links[::-1]

    chapters = []
    for idx, ch_url in enumerate(chapter_links):
        images = scrape_chapter(ch_url)
        if not images:
            continue

        chapters.append({
            "chapter": idx + 1,
            "images": images
        })

        time.sleep(1)

    return title, chapters

# =====================================================
# API UPLOAD
# =====================================================

def upload_batch(title, batch):
    payload = { "title": title, "chapters": batch }

    try:
        r = requests.post(
            f"{API_BASE_URL}/api/stories/create",
            json=payload,
            timeout=20
        )
        if r.status_code == 413:
            print("ERROR 413: Batch quá nặng")
            return None

        print("API RESPONSE:", r.text)
        data = r.json()
        return data.get("storyId")
    except Exception as e:
        print("POST ERROR:", e)
        return None

# =====================================================
# MAIN
# =====================================================

def main():
    stories = load_stories()
    posted_urls = {s["url"] for s in stories}

    found = 0

    for page in range(START_PAGE, MAX_PAGES + 1):

        url = f"https://nettruyen0209.com/?page={page}"
        r = safe_get(url)
        if not r:
            continue

        soup = BeautifulSoup(r.text, "lxml")
        links = [a["href"] for a in soup.select("div.item > a")]

        for story_url in links:

            if story_url in posted_urls:
                continue

            print(f"\n=== SCRAPE STORY: {story_url} ===")

            result = scrape_story(story_url)
            if not result:
                print("Scrape lỗi, bỏ qua.")
                continue

            title, chapters = result
            if not chapters:
                print("Không có chapter scrape được.")
                continue

            # Upload
            storyId = None
            uploaded_chapters = 0

            for i in range(0, len(chapters), BATCH_SIZE):
                batch = chapters[i:i + BATCH_SIZE]

                sid = upload_batch(title, batch)
                if not sid:
                    print("Upload lỗi → dừng truyện này.")
                    storyId = None
                    break

                # Lấy storyId từ batch đầu tiên
                if not storyId:
                    storyId = sid

                uploaded_chapters += len(batch)

            if storyId:
                # Lưu vào stories.json
                stories.append({
                    "url": story_url,
                    "title": title,
                    "storyId": storyId,
                    "chapters_uploaded": uploaded_chapters
                })
                save_stories(stories)

                found += 1
                print(f"✔ DONE {title} — Uploaded {uploaded_chapters} chapters")

                if found >= STORIES_PER_RUN:
                    print("Reached upload limit. DONE.")
                    return

            time.sleep(2)

    print("DONE")

if __name__ == "__main__":
    main()
