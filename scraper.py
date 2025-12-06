import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import quote

# Cấu hình cho nettruyen0209.com
BASE_URL = "https://nettruyen0209.com"
DELAY = 3  # Giây giữa các request
NUM_TRUYEN_QUET = 10  # Quét 10 truyện hot mới nhất

def get_hot_stories():
    """Quét trang chủ/hot lấy danh sách truyện mới nhất – dựa trên HTML thực tế"""
    url = f"{BASE_URL}/truyen-hot"  # Trang hot stories
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        stories = []
        # Selector thực tế từ HTML: dùng 'div.story-item' hoặc 'a[href*="/manga/"]' (dựa trên tool check)
        items = soup.select('div.story-item a[href*="/manga/"], .manga-item a, h3 a, .item a')[:NUM_TRUYEN_QUET]
        for item in items:
            try:
                title = item.get('title') or item.text.strip()
                link = BASE_URL + item['href'] if item['href'].startswith('/') else item['href']
                stories.append({'title': title, 'link': link})
                print(f"Tìm thấy: {title}")
            except Exception as e:
                print(f"Lỗi item: {e}")
                continue
        return stories if stories else []
    except Exception as e:
        print(f"Lỗi quét hot stories: {e}")
        return []

def scrape_story_detail(url):
    """Scrape chi tiết 1 truyện + chapter mới nhất – selector thực tế"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        # Selector thực tế cho title, author, desc, cover
        title_elem = soup.find("h1", class_="title-detail") or soup.find("h1")
        title = title_elem.text.strip() if title_elem else "Không có tên"
        story_id = "".join(c for c in title.lower() if c.isalnum())

        author_elem = soup.find("li", string="Tác giả:") or soup.find("span", class_="author")
        author = author_elem.find_next("a").text.strip() if author_elem else "Không rõ"

        desc_elem = soup.find("div", class_="detail-content") or soup.find("p", class_="desc")
        desc = desc_elem.get_text(strip=True)[:500] + "..." if desc_elem else "Chưa có tóm tắt"

        cover_elem = soup.find("div", class_="col-image") or soup.find("img", class_="cover")
        cover = cover_elem["src"] if cover_elem else ""

        # Chapter mới nhất
        latest_chap = soup.find("a", class_="chapter-row") or soup.find("a", class_="chapter")
        chap_name = latest_chap.text.strip() if latest_chap else "Chapter mới"
        chap_url = BASE_URL + latest_chap["href"] if latest_chap else ""

        time.sleep(DELAY)
        ch_res = requests.get(chap_url, headers=headers, timeout=10)
        ch_soup = BeautifulSoup(ch_res.text, 'html.parser')
        images = []
        for img in ch_soup.find_all("img", class_="page-break") or ch_soup.find_all("img", class_="page"):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if src and src.startswith("http"):
                images.append(src)

        return {
            "id": story_id,
            "title": title,
            "author": author,
            "description": desc,
            "thumbnail": cover,
            "new_chapter": {"name": chap_name, "images": images}
        }
    except Exception as e:
        print(f"Lỗi scrape chi tiết {url}: {e}")
        return None

def update_stories(new_data):
    """Kiểm tra mới/cũ, thêm truyện/chapter mới"""
    if not os.path.exists("stories.json"):
        with open("stories.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    with open("stories.json", "r", encoding="utf-8") as f:
        stories = json.load(f)

    exist = next((s for s in stories if s["id"] == new_data["id"]), None)
    if not exist:
        stories.append({
            "id": new_data["id"],
            "title": new_data["title"],
            "author": new_data["author"],
            "description": new_data["description"],
            "thumbnail": new_data["thumbnail"],
            "chapters": [new_data["new_chapter"]]
        })
        print(f"THÊM TRUYỆN MỚI: {new_data['title']}")
    else:
        if not any(ch["name"] == new_data["new_chapter"]["name"] for ch in exist["chapters"]):
            exist["chapters"].append(new_data["new_chapter"])
            print(f"THÊM CHAPTER MỚI: {new_data['new_chapter']['name']} - {new_data['title']}")
        else:
            print(f"Chapter đã có: {new_data['title']}")

    with open("stories.json", "w", encoding="utf-8") as f:
        json.dump(stories, f, ensure_ascii=False, indent=2)

# MAIN – Tự động quét và cập nhật
if __name__ == "__main__":
    print("Bot bắt đầu quét nettruyen0209.com...")
    hot_list = get_hot_stories()
    print(f"Tìm thấy {len(hot_list)} truyện hot")

    for item in hot_list:
        data = scrape_story_detail(item["link"])
        if data:
            update_stories(data)
        time.sleep(DELAY)

    print("Bot hoàn thành – đã cập nhật stories.json!")
