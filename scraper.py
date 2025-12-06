import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import quote

# Cấu hình
BASE_URL = "https://nettruyen0209.com"
DELAY = 4  # Delay an toàn
NUM_TRUYEN_QUET = 10  # Quét 10 truyện từ trang chủ

def get_hot_stories():
    """Quét trang chủ (/) lấy danh sách 10 truyện mới/hot nhất – selector thực tế"""
    url = BASE_URL + "/"  # Trang chủ thay vì /truyen-hot (vì 404)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        stories = []
        # Selector thực tế: quét từ trang chủ, dùng .story-item, .manga-item, hoặc a[href*="/manga/"]
        items = soup.select('.story-item a[href*="/manga/"], .manga-item a[href*="/manga/"], .item a[href*="/manga/"], h3 a[href*="/manga/"]')[:NUM_TRUYEN_QUET]
        for item in items:
            try:
                title = item.get('title') or item.text.strip()
                if not title or len(title) < 5:
                    continue
                link = BASE_URL + item['href'] if item['href'].startswith('/') else item['href']
                stories.append({'title': title, 'link': link})
                print(f"Tìm thấy: {title}")
            except Exception as e:
                print(f"Lỗi item: {e}")
                continue
        return stories if stories else []
    except Exception as e:
        print(f"Lỗi quét trang chủ: {e}")
        return []

def scrape_story_detail(url):
    """Scrape chi tiết 1 truyện + chapter mới nhất – selector thực tế"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        # Selector thực tế cho title
        title_elem = soup.find("h1", class_="title-detail") or soup.find("h1") or soup.find("title")
        title = title_elem.text.strip() if title_elem else "Không có tên"
        story_id = "".join(c for c in title.lower() if c.isalnum())

        # Author
        author_elem = soup.find("li", string=re.compile("Tác giả")) or soup.find("span", class_="author") or soup.find("div", class_="author")
        author = author_elem.find_next("a").text.strip() if author_elem else "Không rõ"

        # Description
        desc_elem = soup.find("div", class_="detail-content") or soup.find("p", class_="desc") or soup.find("div", class_="summary")
        desc = desc_elem.get_text(strip=True)[:500] + "..." if desc_elem else "Chưa có tóm tắt"

        # Cover
        cover_elem = soup.find("div", class_="col-image") or soup.find("img", class_="cover") or soup.find("img", alt=re.compile(title))
        cover = cover_elem.get("src") if cover_elem else ""

        # Latest chapter
        latest_chap = soup.find("a", class_="chapter-row") or soup.find("a", class_="chapter") or soup.find("li", class_="chapter")
        if not latest_chap:
            print("Không tìm thấy chapter")
            return None
        chap_name = latest_chap.text.strip()
        chap_url = BASE_URL + latest_chap.get("href", "") if latest_chap.get("href") else ""

        time.sleep(DELAY)
        ch_res = requests.get(chap_url, headers=headers, timeout=15)
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

# MAIN
if __name__ == "__main__":
    print("Bot bắt đầu quét nettruyen0209.com...")
    hot_list = get_hot_stories()
    print(f"Tìm thấy {len(hot_list)} truyện hot")

    for item in hot_list:
        data = scrape_story_detail(item["link"])
        if data:
            update_stories(data)
        time.sleep(DELAY)

    print("Bot hoàn thành – cập nhật stories.json!")
