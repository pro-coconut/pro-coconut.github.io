import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import quote
import re

# Cấu hình
NETTRUYEN_BASE = "https://nettruyen0209.com"
DELAY = 3  # Giây giữa các request (chống block)
NUM_TRUYEN_QUET = 10  # Quét 10 truyện mới nhất từ trang chủ

def get_truyen_hot():
    """Quét trang chủ lấy danh sách 10 truyện hot mới nhất"""
    url = f"{NETTRUYEN_BASE}/truyen-tranh-hot"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    truyen_list = []
    for item in soup.find_all('div', class_='item')[:NUM_TRUYEN_QUET]:
        try:
            title = item.find('h3', class_='name').text.strip()
            link = NETTRUYEN_BASE + item.find('a')['href']
            truyen_list.append({'title': title, 'link': link})
        except:
            continue
    
    return truyen_list

def scrape_story(link):
    """Scrape chi tiết 1 truyện (tên, tóm tắt, ảnh bìa, chapter mới nhất)"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    res = requests.get(link, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    try:
        title = soup.find('h1', class_='title-detail').text.strip()
        story_id = re.sub(r'[^a-z0-9]', '', title.lower())
        author = soup.find('span', class_='author').text.strip() if soup.find('span', class_='author') else "Không rõ"
        desc = soup.find('div', class_='detail-content').find('p').text.strip() if soup.find('div', class_='detail-content') else "Chưa có tóm tắt"
        cover = soup.find('div', class_='col-image').find('img')['src']
        
        # Lấy chapter mới nhất
        latest_ch = soup.find('a', class_='chapter-row')
        chap_name = latest_ch.text.strip()
        chap_link = NETTRUYEN_BASE + latest_ch['href']
        
        time.sleep(DELAY)
        ch_res = requests.get(chap_link, headers=headers)
        ch_soup = BeautifulSoup(ch_res.text, 'html.parser')
        images = [img.get('src') or img.get('data-src') for img in ch_soup.find_all('img', class_='page-break') if img.get('src') or img.get('data-src')]
        
        return {
            "id": story_id,
            "title": title,
            "author": author,
            "description": desc,
            "thumbnail": cover,
            "new_chapter": {"name": chap_name, "images": images}
        }
    except Exception as e:
        print(f"Lỗi scrape {link}: {e}")
        return None

def update_stories(new_data):
    """Kiểm tra mới/cũ, thêm truyện/chapter mới vào stories.json"""
    if not os.path.exists("stories.json"):
        with open("stories.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    with open("stories.json", "r", encoding="utf-8") as f:
        stories = json.load(f)

    exist = next((s for s in stories if s["id"] == new_data["id"]), None)
    if not exist:
        # Thêm truyện mới
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
        # Kiểm tra chapter mới
        if not any(ch["name"] == new_data["new_chapter"]["name"] for ch in exist["chapters"]):
            exist["chapters"].append(new_data["new_chapter"])
            print(f"THÊM CHAPTER MỚI: {new_data['new_chapter']['name']} - {new_data['title']}")
        else:
            print(f"Chapter đã có: {new_data['title']}")

    # Lưu lại
    with open("stories.json", "w", encoding="utf-8") as f:
        json.dump(stories, f, ensure_ascii=False, indent=2)

# MAIN – Tự động quét trang chủ NetTruyen0209
if __name__ == "__main__":
    print("Bot bắt đầu quét trang chủ NetTruyen0209...")
    hot_list = get_truyen_hot()
    print(f"Tìm thấy {len(hot_list)} truyện hot mới")

    for item in hot_list:
        story = scrape_story(item['link'])
        if story:
            update_stories(story)
        time.sleep(DELAY)  # Delay giữa các truyện

    print("Bot hoàn thành – cập nhật stories.json!")
