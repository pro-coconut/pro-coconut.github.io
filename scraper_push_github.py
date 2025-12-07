import os
import json
import time
import requests
from bs4 import BeautifulSoup
from git import Repo

# ===== Cấu hình =====
REPO_URL = "https://github.com/pro-coconut/pro-coconut.github.io.git"
BRANCH = "main"
TOKEN = os.environ.get("MY_GITHUB_TOKEN")
if not TOKEN:
    raise ValueError("Missing GitHub token! Add MY_GITHUB_TOKEN in workflow secrets.")

STORIES_FILE = "stories.json"
BASE_LIST_URL = "https://nettruyen0209.com/danh-sach-truyen/{page}/?sort=last_update&status=0"
BASE_MANGA_URL = "https://nettruyen0209.com/manga/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ===== Hàm lấy danh sách truyện =====
def get_story_list(max_pages=5):
    stories = []
    for page in range(4, 4 + max_pages):
        url = BASE_LIST_URL.format(page=page)
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"[WARN] Failed to fetch page {page}")
            continue
        soup = BeautifulSoup(r.text, "lxml")
        for item in soup.select(".list-truyen .truyen-item"):
            title = item.select_one(".truyen-title a").text.strip()
            link = item.select_one(".truyen-title a")["href"]
            slug = link.rstrip("/").split("/")[-1]
            thumbnail = item.select_one("img")["src"]
            stories.append({
                "id": slug,
                "title": title,
                "author": "Không rõ",
                "description": "",
                "thumbnail": thumbnail,
                "link": link
            })
    return stories

# ===== Hàm lấy chapter của truyện =====
def get_chapters(story_link):
    chapters = []
    r = requests.get(story_link, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return chapters
    soup = BeautifulSoup(r.text, "lxml")
    chap_list = soup.select(".list-chapter li a")
    for chap in reversed(chap_list):  # từ chapter 1 trở đi
        chap_name = chap.text.strip()
        chap_url = chap["href"]
        images = get_chapter_images(chap_url)
        if images:
            chapters.append({
                "name": chap_name,
                "images": images
            })
    return chapters

# ===== Hàm lấy ảnh của chapter =====
def get_chapter_images(chap_url):
    r = requests.get(chap_url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    imgs = soup.select(".page-chapter img")
    image_urls = [img["src"] for img in imgs if img.get("src")]
    return image_urls

# ===== Hàm lưu stories.json =====
def save_stories(data):
    with open(STORIES_FILE, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===== Hàm push lên GitHub =====
def push_to_github():
    remote_url_with_token = REPO_URL.replace("https://", f"https://{TOKEN}@")
    repo = Repo(".")
    if "origin" in [r.name for r in repo.remotes]:
        origin = repo.remote("origin")
        origin.set_url(remote_url_with_token)
    else:
        origin = repo.create_remote("origin", remote_url_with_token)

    repo.git.add(STORIES_FILE)
    try:
        repo.git.commit("-m", "Update stories.json")
    except:
        # Không có thay đổi
        pass

    origin.push(refspec=f"{BRANCH}:{BRANCH}")
    print("[DONE] Pushed stories.json to GitHub!")

# ===== Hàm chính =====
def run_scraper():
    print("Fetching story list...")
    story_list = get_story_list(max_pages=3)  # lấy 3 trang ví dụ
    stories_data = []

    for idx, story in enumerate(story_list, 1):
        print(f"Scraping {story['title']} ({idx}/{len(story_list)})")
        chapters = get_chapters(story["link"])
        story_data = {
            "id": story["id"],
            "title": story["title"],
            "author": story["author"],
            "description": story["description"],
            "thumbnail": story["thumbnail"],
            "chapters": chapters
        }
        stories_data.append(story_data)
        time.sleep(1)  # tránh bị block

    save_stories(stories_data)
    push_to_github()

if __name__ == "__main__":
    run_scraper()
