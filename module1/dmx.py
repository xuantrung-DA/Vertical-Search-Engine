import requests
from bs4 import BeautifulSoup
import json
import time
import re

# giả lập trình duyệt gg chrome window 10 -> tránh nhầm là bot
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36"
}
BASE_URL = "https://www.dienmayxanh.com"

def extract_dish_ids(html):
    return re.findall(r'/vao-bep/[^/]+-(\d+)', html)

def get_links_from_ajax(page, listdishid):
    url = BASE_URL + "/vao-bep/aj/Home/ViewMoreLastestBox"
    headers = HEADERS.copy()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    data = {
        "pageindex": page,
        "listdishid": ",".join(listdishid)
    }
    r = requests.post(url, headers=headers, data=data, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.select("a[href^='/vao-bep/']"):
        href = a.get("href")
        if href and not href.startswith("javascript:"):
            full_url = BASE_URL + href
            if full_url not in links:
                links.append(full_url)

    new_ids = extract_dish_ids(r.text)
    return links, new_ids

def get_links_from_main_page():
    url = BASE_URL + "/vao-bep"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    section = soup.select_one("div.hlweek.monmoi")
    if not section:
        print("Không tìm thấy phần món ngon mới nhất.")
        return [], []

    links, dish_ids = [], []
    for a in section.select("a[href^='/vao-bep/']"):
        href = a.get("href")
        if href and not href.startswith("javascript:"):
            full_url = BASE_URL + href
            if full_url not in links:
                links.append(full_url)

    for li in section.select("li[data-id]"):
        dish_id = li.get("data-id")
        if dish_id:
            dish_ids.append(dish_id)

    return links, dish_ids

def get_ingredients(soup):
    return [span.get_text(" ", strip=True) for span in soup.select(".box-detail .staple span") if span.get_text(strip=True)]

def get_instructions(soup_or_rec):
    steps = []

    for li in soup_or_rec.select("li[id^=step]"):
        text_div = li.select_one("div.text-method")
        if not text_div:
            continue
        title = text_div.select_one("h3.txt-method, h3")
        title_text = title.get_text(strip=True) if title else ""
        paras = [p.get_text(strip=True) for p in text_div.find_all("p", recursive=False) if p.get_text(strip=True)]
        if title_text:
            steps.append(title_text)
        steps.extend(paras)

    if not steps:
        for li in soup_or_rec.select(".method ul li"):
            text_div = li.select_one("div.text-method")
            if not text_div:
                continue
            title_el = text_div.select_one("h3, h2")
            title_text = title_el.get_text(strip=True) if title_el else ""
            paras = [p.get_text(strip=True) for p in text_div.select("p") if p.get_text(strip=True)]
            if title_text:
                steps.append(title_text)
            steps.extend(paras)

    return steps if steps else ["(Không tìm thấy hướng dẫn)"]


def scrape_recipe(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    recipes = soup.select("div.box-recipe")

    if recipes: 
        for rec in recipes:
            title = rec.select_one("h2, h3")
            title = title.get_text(strip=True) if title else "(Không có tiêu đề)"
            ingredients = [span.get_text(" ", strip=True) for span in rec.select(".staple span")]
            steps = get_instructions(rec)
            results.append({
                "title": title,
                "ingredients": ingredients,
                "instructions": steps,
                "url": url
            })
    else: 
        title = soup.select_one("h1")
        title = title.get_text(strip=True) if title else "(Không có tiêu đề)"
        results.append({
            "title": title,
            "ingredients": get_ingredients(soup),
            "instructions": get_instructions(soup),
            "url": url
        })

    return results

def crawl_all(max_pages=50, delay=1):
    all_links, seen_links, all_ids = [], set(), set()
    main_links, dish_ids = get_links_from_main_page()
    all_links, seen_links, all_ids = main_links, set(main_links), set(dish_ids)
    print(f"Trang 1: lấy {len(all_links)} links")

    for page in range(2, max_pages + 1):
        try:
            links, new_ids = get_links_from_ajax(page, list(all_ids))
            new = 0
            for link in links:
                if link not in seen_links:
                    all_links.append(link)
                    seen_links.add(link)
                    new += 1
            all_ids.update(new_ids)
            print(f"Trang {page}: lấy {new} links (tổng {len(all_links)})")
            time.sleep(delay)
        except Exception as e:
            print(f"Lỗi khi tải trang {page}:", e)
            break

    print("Tổng số link thu được:", len(all_links))

    results = []
    for idx, url in enumerate(all_links, 1):
        try:
            recipes = scrape_recipe(url)
            results.extend(recipes)
            print(f"[{idx}/{len(all_links)}] {len(recipes)} công thức từ {url}")
            time.sleep(delay)
        except Exception as e:
            print("Lỗi:", url, e)
    with open("dienmayxanh.json", "w", encoding="utf-8") as f: 
        json.dump(results, f, ensure_ascii=False, indent=2) 
    print("Đã lưu", len(results), "công thức vào dienmayxanh.json") 
if __name__ == "__main__": 
    crawl_all(max_pages=100, delay=1)
