import json, requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "vi,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def safe_text(tag):
    return tag.get_text(strip=True) if tag else None

def get_title(soup):
    el = soup.select_one("h1.article-title")
    if el and safe_text(el):
        return safe_text(el)

    # fallback meta title
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()

    if soup.title and soup.title.string:
        return soup.title.string.strip()

    return None

def get_ingredients(soup):
    ings = []
    for span in soup.select(".box-detail .staple span"):
        text = span.get_text(" ", strip=True)  # gộp cả nội dung + small
        if text:
            ings.append(text)
    return ings

def get_instructions(soup):
    steps = []
    for li in soup.select("li[id^=step]"):
        text_div = li.select_one("div.text-method")
        if not text_div:
            continue

        title = text_div.select_one("h3.txt-method")
        title_text = title.get_text(strip=True) if title else ""

        paras = [p.get_text(strip=True) for p in text_div.find_all("p", recursive=False) if p.get_text(strip=True)]

        if title_text and paras:
            step_text = f"{title_text}\n" + "\n".join(paras)
        elif title_text:
            step_text = title_text
        else:
            step_text = "\n".join(paras)

        if step_text.strip():
            steps.append(step_text.strip())

    return steps if steps else ["(Không tìm thấy hướng dẫn)"]

def scrape_recipe(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    title = get_title(soup) or "(Không tìm thấy tiêu đề)"
    ingredients = get_ingredients(soup)
    instructions = get_instructions(soup)

    return {"title": title, "ingredients": ingredients, "instructions": instructions}

if __name__ == "__main__":
    url = "https://www.dienmayxanh.com/vao-bep/2-cach-lam-ca-tim-chien-chay-hap-dan-de-lam-cho-gia-dinh-13861" 
    data = scrape_recipe(url)

    print("Tên món:", data["title"])
    print("\nNguyên liệu:")
    for i in data["ingredients"]:
        print("-", i)
    print("\nCách làm:")
    for idx, s in enumerate(data["instructions"], 1):
        print(f"Bước {idx}: {s}")
