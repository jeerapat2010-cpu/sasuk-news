#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper.py (v2)
ดึงข่าวด้านการแพทย์แผนไทย/แผนจีน/การแพทย์ทางเลือก/สมุนไพร/เทคโนโลยีการแพทย์/เวลเนส/สปา
จาก Hfocus.org และ Google News RSS แล้วจัดหมวดหมู่ตามเนื้อหาจริง (ไม่ใช่แค่ ในประเทศ/ต่างประเทศ)
พร้อมดึงคำโปรยสั้นๆ (summary) มาด้วยถ้ามี

ผลลัพธ์ถูกรวม dedupe จัดเรียงตามวันที่ แล้วเขียนเป็น news.json
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SasukNewsBot/1.0; "
        "+https://github.com/) WISDOM-TTM-NewsBot"
    )
}

REQUEST_DELAY_SEC = 2
REQUEST_TIMEOUT = 15

HFOCUS_BASE = "https://www.hfocus.org"
HFOCUS_TOPIC_PAGES = [
    ("/topics/%E0%B8%82%E0%B9%88%E0%B8%B2%E0%B8%A7", "ข่าว"),
    ("/topics/%E0%B8%AA%E0%B8%B8%E0%B8%82%E0%B8%A0%E0%B8%B2%E0%B8%9E%E0%B8%9B%E0%B8%90%E0%B8%A1%E0%B8%A0%E0%B8%B9%E0%B8%A1%E0%B8%B4", "สุขภาพปฐมภูมิ"),
    ("/topics/%E0%B8%A3%E0%B8%B2%E0%B8%A2%E0%B8%87%E0%B8%B2%E0%B8%99%E0%B8%9E%E0%B8%B4%E0%B9%80%E0%B8%A8%E0%B8%A9", "รายงานพิเศษ"),
    ("/community", "ชุมชนสุขภาพ"),
]

# ---------------------------------------------------------------------
# หมวดหมู่ย่อย (เรียงลำดับความสำคัญ — เฉพาะเจาะจงก่อน ทั่วไปทีหลัง)
# ---------------------------------------------------------------------
CATEGORY_RULES = [
    ("ฝังเข็ม", [
        "ฝังเข็ม", "acupuncture",
    ]),
    ("แพทย์แผนจีน", [
        "แพทย์แผนจีน", "แผนจีน", "traditional chinese medicine", " tcm ", "tcm,", "tcm.",
    ]),
    ("นวดไทย", [
        "นวดไทย", "นวดแผนไทย", "นวดแผนโบราณ",
    ]),
    ("แพทย์แผนไทย", [
        "แพทย์แผนไทย", "การแพทย์แผนไทย", "แผนไทย", "หมอพื้นบ้าน",
    ]),
    ("กัญชา / กัญชง", [
        "กัญชา", "กัญชง", "cannabis",
    ]),
    ("สมุนไพร", [
        "สมุนไพร", "herbal", "พืชสมุนไพร", "gacp", "gmp สมุนไพร",
    ]),
    ("สปา", [
        "สปา", "spa",
    ]),
    ("เวลเนส", [
        "เวลเนส", "wellness", "ท่องเที่ยวเชิงสุขภาพ",
    ]),
    ("เทคโนโลยีการแพทย์", [
        "เทคโนโลยีทางการแพทย์", "เทคโนโลยีการแพทย์", "เมดเทค", "medtech",
        "integrative medicine", "การแพทย์บูรณาการ", "ai การแพทย์",
    ]),
    ("การแพทย์ทางเลือกอื่นๆ", [
        "การแพทย์ทางเลือก", "แพทย์ทางเลือก",
    ]),
]

KEYWORDS_TH = [kw for _, kws in CATEGORY_RULES for kw in kws]

GOOGLE_NEWS_QUERIES = [
    ("แพทย์แผนไทย", "th", "TH"),
    ("นวดแผนไทย", "th", "TH"),
    ("สมุนไพรไทย", "th", "TH"),
    ("แพทย์แผนจีน", "th", "TH"),
    ("ฝังเข็ม รักษาโรค", "th", "TH"),
    ("กัญชาทางการแพทย์", "th", "TH"),
    ("สปา เวลเนส ไทย", "th", "TH"),
    ("traditional Chinese medicine research", "en", "US"),
    ("herbal medicine wellness industry", "en", "US"),
    ("acupuncture clinical study", "en", "US"),
    ("spa wellness tourism", "en", "US"),
    ("integrative medicine technology", "en", "US"),
]

OUTPUT_FILE = "news.json"
MAX_ITEMS_PER_SOURCE = 15
MAX_TOTAL_ITEMS = 150

# ---------------------------------------------------------------------
# ดึงภาพประกอบจริงจากบทความ — เฉพาะข่าวใน N วันล่าสุด และจำกัดจำนวนครั้ง
# เพื่อไม่ให้ scraper ใช้เวลานานเกินไปหรือโหลดเว็บต้นทางหนักเกินจำเป็น
# ---------------------------------------------------------------------
RECENT_IMAGE_DAYS = 7
MAX_IMAGE_FETCHES = 40
OG_IMAGE_TIMEOUT = 6
IMAGE_FETCH_DELAY_SEC = 0.4

TAG_RE = re.compile(r"<[^>]+>")


def clean_html(text):
    if not text:
        return ""
    text = TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def categorize(title):
    """คืนชื่อหมวดหมู่แรกที่ตรงกับ keyword ในหัวข้อข่าว"""
    title_lower = title.lower()
    for category_name, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.lower().strip() in title_lower:
                return category_name
    return "ข่าวสุขภาพทั่วไป"


def region_of(lang):
    return "ต่างประเทศ" if lang == "en" else "ในประเทศ"


def is_recent(item, days=RECENT_IMAGE_DAYS):
    """เช็คว่าข่าวนี้อยู่ในช่วง N วันล่าสุดไหม (ใช้ตัดสินใจว่าจะดึงภาพจริงหรือไม่)"""
    if item.get("source") == "Hfocus":
        # หน้า topic ของ Hfocus แสดงเฉพาะข่าวล่าสุดอยู่แล้ว และเรารู้แค่ปี-เดือน
        # (ไม่รู้วันที่จริงจาก URL) จึงถือว่าทุกข่าวที่ scrape มาจาก Hfocus เป็นข่าวใหม่เสมอ
        return True

    date_str = item.get("date")
    if not date_str:
        return False
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    return d >= cutoff


def fetch_og_image(url):
    """ดึงภาพปก (og:image / twitter:image) จากหน้าบทความจริง คืนค่า None ถ้าดึงไม่ได้"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=OG_IMAGE_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # บางลิงก์จาก Google News ยังค้างอยู่ที่หน้า redirect ของ Google เอง
    # (ไม่ใช่ HTTP redirect ปกติ แต่เป็น meta refresh) ลองตามลิงก์จริงอีกหนึ่งชั้น
    if "news.google.com" in resp.url:
        refresh_tag = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
        if refresh_tag and refresh_tag.get("content"):
            match = re.search(r"url=['\"]?([^'\">]+)", refresh_tag["content"], re.I)
            if match:
                try:
                    resp2 = requests.get(match.group(1), headers=HEADERS, timeout=OG_IMAGE_TIMEOUT, allow_redirects=True)
                    resp2.raise_for_status()
                    soup = BeautifulSoup(resp2.text, "html.parser")
                except requests.RequestException:
                    pass

    for attrs in (
        {"property": "og:image"},
        {"name": "og:image"},
        {"property": "twitter:image"},
        {"name": "twitter:image"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"]
    return None


def enrich_recent_items_with_images(items):
    """ดึงภาพจริงให้เฉพาะข่าวใน RECENT_IMAGE_DAYS วันล่าสุดที่ยังไม่มีรูป
    จำกัดจำนวนครั้งด้วย MAX_IMAGE_FETCHES เพื่อคุมเวลารันและโหลดของเว็บต้นทาง"""
    fetched = 0
    success = 0
    for item in items:
        if fetched >= MAX_IMAGE_FETCHES:
            break
        if item.get("image"):
            continue
        if not is_recent(item):
            continue

        fetched += 1
        img = fetch_og_image(item["link"])
        if img:
            item["image"] = img
            success += 1
        time.sleep(IMAGE_FETCH_DELAY_SEC)

    print(f"[image] ลองดึงภาพประกอบ {fetched} ข่าว (เฉพาะ {RECENT_IMAGE_DAYS} วันล่าสุด) สำเร็จ {success} ข่าว")
    return items


# ---------------------------------------------------------------------
# Hfocus scraper
# ---------------------------------------------------------------------

def parse_hfocus_topic_page(path, topic_label):
    url = urljoin(HFOCUS_BASE, path)
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[hfocus] ดึงหน้า {url} ไม่สำเร็จ: {e}")
        return items

    soup = BeautifulSoup(resp.text, "html.parser")
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
            continue

        seen_hrefs.add(href)
        full_url = urljoin(HFOCUS_BASE, href)

        date_match = re.search(r"/content/(\d{4})/(\d{2})/", href)
        approx_date = f"{date_match.group(1)}-{date_match.group(2)}-01" if date_match else None

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
            "category": categorize(title_text),
            "region": "ในประเทศ",
            "topic_page": topic_label,
            "image": image_url,
            "summary": "",
            "date": approx_date,
            "id": hashlib.md5(full_url.encode("utf-8")).hexdigest(),
        })

    return items


def filter_by_keywords(items, keywords):
    filtered = []
    for item in items:
        title_lower = item["title"].lower()
        if any(kw.lower().strip() in title_lower for kw in keywords):
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


# ---------------------------------------------------------------------
# Google News RSS
# ---------------------------------------------------------------------

def fetch_google_news_rss(query, lang="th", country="TH"):
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
        date_str = (
            datetime.datetime(*published[:6]).strftime("%Y-%m-%d")
            if published else None
        )

        source_title = None
        if "source" in entry and hasattr(entry.source, "get"):
            source_title = entry.source.get("title")
        elif "source" in entry:
            source_title = getattr(entry.source, "title", None)

        summary_raw = entry.get("summary", "")
        summary = clean_html(summary_raw)
        # ตัด summary ให้สั้นกระชับ
        if len(summary) > 140:
            summary = summary[:140].rsplit(" ", 1)[0] + "…"

        items.append({
            "title": title,
            "link": link,
            "source": source_title or "Google News",
            "category": categorize(title),
            "region": region_of(lang),
            "topic_page": None,
            "image": None,
            "summary": summary,
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


# ---------------------------------------------------------------------
# รวมผล / dedupe / เรียงลำดับ / สถิติ
# ---------------------------------------------------------------------

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
    return sorted(items, key=sort_key, reverse=True)[:max_total]


def build_category_counts(items):
    counts = {}
    for item in items:
        cat = item.get("category", "ข่าวสุขภาพทั่วไป")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def main():
    print("=== เริ่มดึงข่าว สาสุข TTM/เวลเนส ===")

    hfocus_items = fetch_hfocus_news()
    google_items = fetch_all_google_news()

    merged = merge_and_dedupe(hfocus_items, google_items)
    final_items = sort_and_trim(merged)

    final_items = enrich_recent_items_with_images(final_items)

    sources = sorted(set(i["source"] for i in final_items))

    output = {
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "total_items": len(final_items),
        "source_count": len(sources),
        "sources": sources,
        "category_counts": build_category_counts(final_items),
        "items": final_items,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"=== เสร็จสิ้น: เขียน {len(final_items)} รายการลง {OUTPUT_FILE} ===")


if __name__ == "__main__":
    main()
