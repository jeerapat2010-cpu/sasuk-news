#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper.py
ดึงข่าวด้านการแพทย์แผนไทย/แผนจีน/การแพทย์ทางเลือก/สมุนไพร/เทคโนโลยีการแพทย์/เวลเนส/สปา
จาก 2 แหล่ง:
  1. Hfocus.org  -> scrape หน้า topics โดยตรง แล้วกรองด้วย keyword
  2. Google News RSS -> ดึงตาม keyword query ครอบคลุมทั้งข่าวไทยและต่างประเทศ

ผลลัพธ์ถูกรวม dedupe จัดเรียงตามวันที่ แล้วเขียนเป็น news.json
ให้หน้า index.html เอาไปแสดงผล

หมายเหตุ: สคริปต์นี้ถูกออกแบบให้รันบน GitHub Actions (มีอินเทอร์เน็ตเต็มรูปแบบ)
ถ้ารันแล้วได้ผลลัพธ์ว่างเปล่าจากฝั่ง Hfocus ให้ตรวจสอบว่าโครงสร้าง HTML
ของเว็บเปลี่ยนไปหรือไม่ (ดู view-source แล้วปรับ selector ในฟังก์ชัน
parse_hfocus_topic_page ตามความเหมาะสม)
"""

import json
import re
import time
import hashlib
import datetime
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
import feedparser

# -----------------------------------------------------------------------
# ตั้งค่า
# -----------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SasukNewsBot/1.0; "
        "+https://github.com/) WISDOM-TTM-NewsBot"
    )
}

REQUEST_DELAY_SEC = 2  # หน่วงเวลาระหว่าง request แต่ละครั้ง เพื่อไม่ยิงถี่เกินไป
REQUEST_TIMEOUT = 15

# หน้า topics ของ Hfocus ที่จะ scrape (หน้าไหนมีข่าวเยอะก็ยิ่งดี)
HFOCUS_BASE = "https://www.hfocus.org"
HFOCUS_TOPIC_PAGES = [
    ("/topics/%E0%B8%82%E0%B9%88%E0%B8%B2%E0%B8%A7", "ข่าว"),
    ("/topics/%E0%B8%AA%E0%B8%B8%E0%B8%82%E0%B8%A0%E0%B8%B2%E0%B8%9E%E0%B8%9B%E0%B8%90%E0%B8%A1%E0%B8%A0%E0%B8%B9%E0%B8%A1%E0%B8%B4", "สุขภาพปฐมภูมิ"),
    ("/topics/%E0%B8%A3%E0%B8%B2%E0%B8%A2%E0%B8%87%E0%B8%B2%E0%B8%99%E0%B8%9E%E0%B8%B4%E0%B9%80%E0%B8%A8%E0%B8%A9", "รายงานพิเศษ"),
    ("/community", "ชุมชนสุขภาพ"),
]

# keyword ที่ใช้กรองข่าวจาก Hfocus (ต้องเจอคำใดคำหนึ่งในหัวข้อข่าว)
KEYWORDS_TH = [
    "แพทย์แผนไทย", "การแพทย์แผนไทย", "แผนไทย",
    "แพทย์แผนจีน", "แผนจีน", "ฝังเข็ม",
    "การแพทย์ทางเลือก", "แพทย์ทางเลือก",
    "สมุนไพร", "กัญชา", "กัญชง",
    "นวดไทย", "นวดแผนไทย",
    "เวลเนส", "wellness",
    "สปา", "spa",
    "เทคโนโลยีทางการแพทย์", "เทคโนโลยีการแพทย์", "เมดเทค", "medtech",
    "GACP", "GMP", "GDP สมุนไพร",
]

# คำค้นสำหรับ Google News RSS (ครอบคลุมทั้งไทยและต่างประเทศ)
GOOGLE_NEWS_QUERIES = [
    # ภาษาไทย
    ("แพทย์แผนไทย", "th", "TH"),
    ("สมุนไพรไทย", "th", "TH"),
    ("แพทย์แผนจีน ฝังเข็ม", "th", "TH"),
    ("กัญชาทางการแพทย์", "th", "TH"),
    ("เวลเนส สปา ไทย", "th", "TH"),
    # ภาษาอังกฤษ / ต่างประเทศ
    ("traditional Chinese medicine research", "en", "US"),
    ("herbal medicine wellness industry", "en", "US"),
    ("acupuncture clinical study", "en", "US"),
    ("spa wellness tourism", "en", "US"),
    ("integrative medicine technology", "en", "US"),
]

OUTPUT_FILE = "news.json"
MAX_ITEMS_PER_SOURCE = 15
MAX_TOTAL_ITEMS = 150


# -----------------------------------------------------------------------
# Hfocus scraper
# -----------------------------------------------------------------------

def parse_hfocus_topic_page(path, category_label):
    """ดึงและ parse ข่าวจากหน้า topic หนึ่งหน้าของ Hfocus"""
    url = urljoin(HFOCUS_BASE, path)
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[hfocus] ดึงหน้า {url} ไม่สำเร็จ: {e}")
        return items

    soup = BeautifulSoup(resp.text, "html.parser")

    # การ์ดข่าวของ Hfocus เป็นลิงก์ไปที่ /content/YYYY/MM/NNNNN
    content_link_pattern = re.compile(r"^/content/\d{4}/\d{2}/\d+")

    seen_hrefs = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not content_link_pattern.match(href):
            continue
        if href in seen_hrefs:
            continue

        title_text = a_tag.get_text(strip=True)
        if not title_text:
            # ลิงก์นี้อาจเป็นลิงก์รูปภาพ (ไม่มี text) ข้ามไป
            continue

        seen_hrefs.add(href)

        full_url = urljoin(HFOCUS_BASE, href)

        # หาวันที่แบบคร่าวๆ จาก path (/content/YYYY/MM/...)
        date_match = re.search(r"/content/(\d{4})/(\d{2})/", href)
        if date_match:
            approx_date = f"{date_match.group(1)}-{date_match.group(2)}-01"
        else:
            approx_date = None

        # พยายามหารูปภาพที่อยู่ใกล้ๆ ลิงก์นี้ (การ์ดเดียวกัน)
        image_url = None
        parent = a_tag.find_parent()
        if parent:
            img_tag = parent.find_previous("img") or parent.find("img")
            if img_tag and img_tag.get("src"):
                image_url = urljoin(HFOCUS_BASE, img_tag["src"])

        items.append({
            "title": title_text,
            "link": full_url,
            "source": "Hfocus",
            "category": category_label,
            "image": image_url,
            "date": approx_date,
            "id": hashlib.md5(full_url.encode("utf-8")).hexdigest(),
        })

    return items


def filter_by_keywords(items, keywords):
    """กรองเฉพาะข่าวที่หัวข้อมี keyword ที่สนใจ"""
    filtered = []
    for item in items:
        title_lower = item["title"].lower()
        if any(kw.lower() in title_lower for kw in keywords):
            filtered.append(item)
    return filtered


def fetch_hfocus_news():
    all_items = []
    for path, label in HFOCUS_TOPIC_PAGES:
        print(f"[hfocus] กำลังดึงหน้า: {label}")
        page_items = parse_hfocus_topic_page(path, label)
        print(f"[hfocus]   พบข่าวทั้งหมด {len(page_items)} รายการในหน้านี้")
        all_items.extend(page_items)
        time.sleep(REQUEST_DELAY_SEC)

    relevant = filter_by_keywords(all_items, KEYWORDS_TH)
    print(f"[hfocus] ข่าวที่ตรง keyword ที่สนใจ: {len(relevant)} รายการ")
    return relevant


# -----------------------------------------------------------------------
# Google News RSS
# -----------------------------------------------------------------------

def fetch_google_news_rss(query, lang="th", country="TH"):
    """ดึงข่าวจาก Google News RSS ตาม query ที่กำหนด"""
    encoded_query = quote(query)
    url = (
        f"https://news.google.com/rss/search?q={encoded_query}"
        f"&hl={lang}&gl={country}&ceid={country}:{lang}"
    )
    items = []
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"[google-news] ดึง RSS ไม่สำเร็จสำหรับ '{query}': {e}")
        return items

    for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
        link = entry.get("link", "")
        title = entry.get("title", "").strip()
        if not title or not link:
            continue

        published = entry.get("published_parsed")
        if published:
            date_str = datetime.datetime(*published[:6]).strftime("%Y-%m-%d")
        else:
            date_str = None

        source_title = None
        if "source" in entry and hasattr(entry.source, "get"):
            source_title = entry.source.get("title")
        elif "source" in entry:
            source_title = getattr(entry.source, "title", None)

        items.append({
            "title": title,
            "link": link,
            "source": source_title or "Google News",
            "category": "ต่างประเทศ" if lang == "en" else "ในประเทศ",
            "image": None,
            "date": date_str,
            "id": hashlib.md5(link.encode("utf-8")).hexdigest(),
        })

    return items


def fetch_all_google_news():
    all_items = []
    for query, lang, country in GOOGLE_NEWS_QUERIES:
        print(f"[google-news] กำลังดึง query: {query} ({lang}-{country})")
        items = fetch_google_news_rss(query, lang, country)
        print(f"[google-news]   พบ {len(items)} รายการ")
        all_items.extend(items)
        time.sleep(1)
    return all_items


# -----------------------------------------------------------------------
# รวมผล / dedupe / เรียงลำดับ
# -----------------------------------------------------------------------

def merge_and_dedupe(*item_lists):
    merged = {}
    for items in item_lists:
        for item in items:
            key = item["id"]
            if key not in merged:
                merged[key] = item
    return list(merged.values())


def sort_and_trim(items, max_total=MAX_TOTAL_ITEMS):
    def sort_key(item):
        return item.get("date") or "0000-00-00"

    items_sorted = sorted(items, key=sort_key, reverse=True)
    return items_sorted[:max_total]


# -----------------------------------------------------------------------
# main
# -----------------------------------------------------------------------

def main():
    print("=== เริ่มดึงข่าว สาสุข TTM/เวลเนส ===")

    hfocus_items = fetch_hfocus_news()
    google_items = fetch_all_google_news()

    merged = merge_and_dedupe(hfocus_items, google_items)
    final_items = sort_and_trim(merged)

    output = {
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "total_items": len(final_items),
        "items": final_items,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"=== เสร็จสิ้น: เขียน {len(final_items)} รายการลง {OUTPUT_FILE} ===")


if __name__ == "__main__":
    main()
