import os
import json
import time
import requests
from bs4 import BeautifulSoup

API_BASE_URL = os.getenv("API_BASE_URL")
START_PAGE = int(os.getenv("START_PAGE", 1))
STORIES_PER_RUN = int(os.getenv("STORIES_PER_RUN", 3))
MAX_PAGES = int(os.getenv("MAX_PAGES", 20))
BATCH_SIZE = 5  # batch chapter per API call

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

POSTED_FILE = "posted.json"

# --------------------------------
# Utilities
# --------------------------------

def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []
    with open(POSTED_FILE, "r", encoding="utf8") as f:
        return json.load(f)

def save_posted(data):
    with open(POSTED_FILE, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_get(url):
    """Request an URL with retry + timeout."""
    for i in range(5):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r
            time.sleep(2)
        except:
            time.sleep(2)
    return None

# --------------------------------
# Scrape chapter content
# --------------------------------

def scrape_chapter(url):
    r = safe_get(url)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select("div.page-chapter > img")

    return [img.get("src") for img in imgs if img.get("src")]

# --------------------------------
# Scrape story (multiple chapters)
# --------------------------------

def scrape_story(story_url):
    r = safe_get(story_url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "lxml")
    title = soup.select_one("h1.title-detail").text.strip()

    chapter_links = [
        a["href"] for a in soup.select("ul.list-chapter a")
        if a.get("href")
    ]

    chapters = []
    chapter_links = chapter_links[::-1]  # sort from old → new

    for idx, ch_url in enumerate(chapter_links):
        images = scrape_chapter(ch_url)
        chapter_num = idx + 1

        if len(images) <= 0:
            continue  # skip lỗi

        chapters.append({
            "chapter": chapter_num,
            "images": images,
        })

        time.sleep(2)

    return title, chapters

# --------------------------------
# API Upload (batch)
# --------------------------------

def upload_batch(title, batch):
    payload = {
        "title": title,
        "chapters": batch,
    }

    try:
        r = requests.post(
            f"{API_BASE_URL}/api/stories/create",
            json=payload,
            timeout=20
        )
        if r.status_code == 413:
            print("ERROR 413 — batch quá nặng → giảm batch size")
            return False
        print("API RESPONSE:", r.text)
        return r.status_code == 200
    except Exception as e:
        print("POST ERROR:", e)
        return False

# --------------------------------
# MAIN
# --------------------------------

def main():
    posted = load_posted()
    found_count = 0

    for page in range(START_PAGE, MAX_PAGES + 1):
        url = f"https://nettruyen0209.com/?page={page}"
        r = safe_get(url)
        if not r:
            continue

        soup = BeautifulSoup(r.text, "lxml")
        links = [a["href"] for a in soup.select("div.item > a")]

        for story in links:
            if story in posted:
                continue

            print(f"\n=== SCRAPE STORY: {story} ===")

            title, all_chapters = scrape_story(story)
            if not all_chapters:
                print("No chapter scraped, skip.")
                continue

            # Batch upload
            for i in range(0, len(all_chapters), BATCH_SIZE):
                batch = all_chapters[i:i + BATCH_SIZE]
                ok = upload_batch(title, batch)
                if not ok:
                    print("Batch upload failed – skipping story.")
                    break

            # Mark as posted
            posted.append(story)
            save_posted(posted)

            found_count += 1
            if found_count >= STORIES_PER_RUN:
                print("Reached limit. DONE.")
                return

            time.sleep(3)

    print("DONE.")

if __name__ == "__main__":
    main()
