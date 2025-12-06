import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from urllib.parse import quote

# Cấu hình
BASE_URL = "https://nettruyen0209.com"
DELAY = 4  # Delay an toàn
NUM_TRUYEN_QUET = 15  # Quét 15 truyện từ trang chủ + phân trang

def get_all_stories():
    """Quét trang chủ (/) + phân trang để lấy danh sách truyện – tránh 404"""
    stories = []
    page = 1
    while len(stories) < NUM_TRUYEN_QUET:
        url = f"{BASE_URL}/?page={page}"  # Quét trang chủ với phân trang (trang 1, 2, 3...)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 404:
                print(f"Trang {page} không tồn tại, dừng quét")
                break
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            
            items = soup.select('.story-item a[href*="/manga/"], .manga-item a, .item a, h3 a, li a')[:5]  # 5/trang
            if not items:
                print(f"Không có truyện ở trang {page}, dừng quét")
                break
            
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
            
            page += 1
            time.sleep(DELAY)
        except Exception as e:
            print(f"Lỗi quét trang {page}: {e}")
            break
    
    print(f"Tổng quét được {len(stories)} truyện từ trang chủ + phân trang")
    return stories

def scrape_story_detail(url):
    """Scrape chi tiết 1 truyện + chapter mới nhất"""
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

        # Title
        title_elem = soup.find("h1", class_="title-detail") or soup.find("h1") or soup.find("title")
        title = title_elem.text.strip() if title_elem else "Không có tên"
        story_id = re.sub(r'[^a-z0-9]', '', title.lower())

        # Author
        author_elem = soup.find("li", string=re.compile("Tác giả")) or soup.find("span", class_="author") or soup.find("div", class_="author")
        author = author_elem.find_next("a").text.strip() if author_elem else "Không rõ"

        # Description
        desc_elem = soup.find("div", class_="detail-content") or soup.find("p", class_="desc") or soup.find("div", class_="summary")
        desc = desc_elem.get_text(strip=True)[:500] + "..." if desc_elem else "Chưa có tóm tắt"

        # Cover
        cover_elem = soup.find("div", class_="col-image") or soup.find("img", class_="cover") or soup.find("img", alt=re.compile(title, re.I))
        cover = cover_elem.get("src") if cover_elem and cover_elem.get("src") else ""

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

# MAIN – Quét từ trang chủ + phân trang
if __name__ == "__main__":
    print("Bot bắt đầu quét nettruyen0209.com...")
    hot_list = get_all_stories()
    print(f"Tìm thấy {len(hot_list)} truyện từ trang chủ + phân trang")

    for item in hot_list:
        data = scrape_story_detail(item["link"])
        if data:
            update_stories(data)
        time.sleep(DELAY)

    print("Bot hoàn thành – cập nhật stories.json!")
