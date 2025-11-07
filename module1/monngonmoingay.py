import json, time, math
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================== CẤU HÌNH ==================
BASE_URL   = "https://monngonmoingay.com"
LIST_PATH  = "/tim-kiem-mon-ngon/"
PER_PAGE   = 36          # số món / trang của site
MAX_PAGES  = 68          # crawl bao nhiêu trang phân trang
MAX_WORKERS = 4          # số driver chạy song song (3-5 là hợp lý)
HEADLESS   = True        # nên bật khi chạy song song

# ================== DRIVER HELPERS ==================
def make_options():
    opts = webdriver.ChromeOptions()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1366,850")
    opts.add_argument("--log-level=3")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    # tắt ảnh/notification để nhanh
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    opts.add_experimental_option("prefs", prefs)
    return opts

def make_driver():
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=make_options())

def wait_ready(driver, timeout=30):
    WebDriverWait(driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")

def dedup_keep_order(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            out.append(x); seen.add(x)
    return out

# ================== LẤY LINK Ở TRANG DANH SÁCH ==================
def build_list_url(page: int) -> str:
    if page <= 1:
        return f"{BASE_URL}{LIST_PATH}?pagenum={PER_PAGE}"
    return f"{BASE_URL}{LIST_PATH}page/{page}/?pagenum={PER_PAGE}"

def get_detail_links_from_list_page(driver, list_url: str):
    driver.get(list_url)
    wait_ready(driver)

    links = []
    t0 = time.time()
    while time.time() - t0 < 10:
        driver.execute_script("window.scrollBy(0, 900)")
        time.sleep(0.35)
        links = driver.execute_script("""
            return Array.from(document.querySelectorAll('a[href]'))
                .filter(a => a.textContent.toLowerCase().includes('xem chi tiết'))
                .map(a => a.href);
        """)
        links = [l for l in links if l.startswith(BASE_URL)]
        if links:
            break
    return dedup_keep_order(links)

def collect_all_links(max_pages=1):
    driver = make_driver()
    try:
        all_links = []
        for p in range(1, max_pages + 1):
            url = build_list_url(p)
            links = get_detail_links_from_list_page(driver, url)
            print(f"Trang {p}: {len(links)} link")
            all_links.extend(links)
        return dedup_keep_order(all_links)
    finally:
        driver.quit()

# ================== PARSE CHI TIẾT (driver theo từng thread) ==================
def _normalize_lines(text: str):
    return [ln.strip() for ln in text.split("\n") if ln.strip()]

def block_list_after_heading(driver, heading_text):
    heads = driver.find_elements(
        By.XPATH,
        f"//h2[contains(., '{heading_text}')]"
        f"|//h3[contains(., '{heading_text}')]"
        f"|//h4[contains(., '{heading_text}')]"
    )
    if not heads:
        return []
    h = heads[0]
    node = None
    for xp in [
        "following-sibling::*[self::div or self::ul or self::ol or self::p][1]",
        "following-sibling::*[1]"
    ]:
        try:
            node = h.find_element(By.XPATH, xp)
            break
        except:
            node = None
    if node is None:
        return []

    lis = node.find_elements(By.XPATH, ".//li[normalize-space()]")
    if lis:
        return [li.text.strip() for li in lis]
    parts = node.find_elements(By.XPATH, ".//p | .//div | .//span")
    texts = [p.text.strip() for p in parts if p.text.strip()]
    if texts:
        return texts
    return _normalize_lines(node.text)

def ingredients_list(driver):
    # section nguyen lieu
    section = None
    try:
        section = WebDriverWait(driver, 8).until(EC.presence_of_element_located((
            By.XPATH,
            "//*[contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'nguyenlieu') or "
            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'nguyenlieu')]"
        )))
    except:
        pass

    containers = []
    if section:
        containers = section.find_elements(
            By.XPATH,
            ".//*[contains(@class,'block-nguyenlieu') and contains(@class,'tab-content') and not(contains(@class,'hidden'))]"
        )
    if not containers:
        containers = driver.find_elements(
            By.XPATH,
            "//*[contains(@class,'block-nguyenlieu') and contains(@class,'tab-content') and not(contains(@class,'hidden'))]"
        )

    for cont in containers:
        lis = cont.find_elements(By.XPATH, ".//li[normalize-space()]")
        if lis:
            return [li.text.strip() for li in lis]
        parts = cont.find_elements(By.XPATH, ".//p | .//div | .//span")
        texts = [p.text.strip() for p in parts if p.text.strip()]
        if texts:
            return texts
        if cont.text.strip():
            return _normalize_lines(cont.text)

    for key in ["Thành phần nguyên liệu", "Nguyên liệu"]:
        lst = block_list_after_heading(driver, key)
        if lst:
            return lst

    try:
        table = driver.find_element(
            By.XPATH,
            "//table[.//th[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'nguyên liệu') or contains(., 'Thành phần')]]"
        )
        rows = table.find_elements(By.XPATH, ".//tr[td]")
        pairs = []
        for r in rows:
            tds = r.find_elements(By.XPATH, "./td")
            if not tds: continue
            name = tds[0].text.strip()
            qty  = tds[1].text.strip() if len(tds) > 1 else ""
            if name:
                pairs.append(f"{name}" + (f" — {qty}" if qty else ""))
        if pairs:
            return pairs
    except:
        pass
    return []

def scrape_one(link):
    """Worker: mỗi link dùng 1 driver riêng, trả về dict."""
    d = make_driver()
    try:
        d.get(link)
        wait_ready(d)
        try:
            WebDriverWait(d, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            title = d.find_element(By.TAG_NAME, "h1").text.strip()
        except:
            try:
                title = d.find_element(By.TAG_NAME, "h2").text.strip()
            except:
                title = "(không tiêu đề)"

        ing   = ingredients_list(d)
        so    = block_list_after_heading(d, "Sơ Chế")
        thuc  = block_list_after_heading(d, "Thực Hiện")
        dung  = block_list_after_heading(d, "Cách Dùng")
        instructions = [*so, *thuc, *dung]  # gộp 3 mục

        return {
            "title": title,
            "ingredients": ing,
            "instructions": instructions,
            "url": link
        }
    finally:
        d.quit()

# ================== MAIN ==================
if __name__ == "__main__":
    all_links = collect_all_links(MAX_PAGES)
    print(f"Tổng số link thu được: {len(all_links)}")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        fut2link = {ex.submit(scrape_one, l): l for l in all_links}
        for i, fut in enumerate(as_completed(fut2link), 1):
            link = fut2link[fut]
            try:
                rec = fut.result()
                results.append(rec)
                print(f"[{i}/{len(all_links)}] OK: {rec['title']}")
            except Exception as e:
                print(f"[{i}/{len(all_links)}] FAIL: {link} -> {e}")

    with open("monngonmoingay_multi.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu {len(results)} công thức vào monngonmoingay_multi.json")
