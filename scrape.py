"""
A股董秘说 — GitHub Actions 独立爬虫脚本
每次运行：爬取最新数据 → 合并到 data/all_qa.json → 生成 hot.json + stats.json
"""
import json, os, re, time, random, logging
from datetime import datetime

try:
    from curl_cffi import requests as cf_requests
    USE_CURL = True
except ImportError:
    import requests as cf_requests
    USE_CURL = False

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call(["pip3", "install", "beautifulsoup4", "lxml"])
    from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

IMPERSONATE = "chrome110" if USE_CURL else None
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SSE_UID_FILE = os.path.join(DATA_DIR, "sse_uid_map.json")

CNINFO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://irm.cninfo.com.cn/f/index",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
SSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "http://sns.sseinfo.com/",
}


def _req(method, url, data=None, params=None, headers=None, timeout=15):
    kw = {"timeout": timeout}
    if USE_CURL:
        kw["impersonate"] = IMPERSONATE
    if headers: kw["headers"] = headers
    if params: kw["params"] = params
    if data: kw["data"] = data
    if method.upper() == "POST":
        return cf_requests.post(url, **kw)
    return cf_requests.get(url, **kw)


def _ts(ts_ms):
    if not ts_ms: return ""
    try: return datetime.fromtimestamp(int(ts_ms)/1000).strftime("%Y-%m-%d %H:%M")
    except: return str(ts_ms)


def _clean(text):
    if not text: return ""
    text = re.sub(r"<[^>]+>", "", text)
    for e, c in [("&nbsp;"," "),("&lt;","<"),("&gt;",">"),("&amp;","&"),("\r",""),("\n"," ")]:
        text = text.replace(e, c)
    return text.strip()


# ─── CNINFO (深交所) ───
def fetch_cninfo(page=1, page_size=50):
    url = "https://irm.cninfo.com.cn/newircs/index/search"
    payload = f"keyword=&pageNum={page}&pageSize={page_size}&contentTypes=11"
    try:
        r = _req("POST", url, data=payload, headers=CNINFO_HEADERS)
        r.raise_for_status()
        raw = r.json()
        rows = []
        for it in raw.get("results", []):
            ans = _clean(it.get("attachedContent", ""))
            if not ans: continue
            rows.append({
                "id": it.get("indexId", ""),
                "stock_code": it.get("stockCode", ""),
                "stock_name": it.get("companyShortName", ""),
                "question": _clean(it.get("mainContent", "")),
                "answer": ans,
                "pub_date": _ts(it.get("pubDate")),
                "reply_date": _ts(it.get("attachedPubDate")),
                "source": "深交所互动易",
                "url": f"https://irm.cninfo.com.cn/f/question/{it.get('indexId','')}",
            })
        return rows, len(raw.get("results", []))
    except Exception as e:
        logger.error(f"CNINFO error: {e}")
        return [], 0


# ─── SSE (上交所) ───
def load_sse_map():
    if os.path.exists(SSE_UID_FILE):
        with open(SSE_UID_FILE, "r") as f:
            return json.load(f)
    return {}


def fetch_sse_qa(stock_code, uid, page_size=10):
    url = "http://sns.sseinfo.com/ajax/userfeeds.do"
    data = {"typeCode":"company","type":"11","pageSize":str(page_size),"uid":str(uid),"page":"1"}
    try:
        r = _req("POST", url, data=data, headers=SSE_HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        rows = []
        for item in soup.find_all("div", class_="m_feed_item"):
            txt = item.find_all("div", class_="m_feed_txt")
            if len(txt) < 2: continue
            q = _clean(txt[0].get_text(strip=True))
            a = _clean(txt[1].get_text(strip=True))
            if not a: continue
            froms = item.find_all("div", class_="m_feed_from")
            q_date = _clean(froms[0].get_text(strip=True)).split(" ")[0] if froms else ""
            a_date = _clean(froms[1].get_text(strip=True)).split(" ")[0] if len(froms)>1 else ""
            rows.append({
                "id": item.get("id", f"{stock_code}_{len(rows)}"),
                "stock_code": stock_code,
                "stock_name": stock_code,
                "question": q, "answer": a,
                "pub_date": q_date, "reply_date": a_date,
                "source": "上证e互动",
                "url": f"http://sns.sseinfo.com/company.do?uid={uid}",
            })
        return rows
    except Exception as e:
        logger.error(f"SSE {stock_code} error: {e}")
        return []


def scrape_all():
    """主爬取函数：抓取最新数据并合并"""
    new_rows = []

    # 1. 深交所前5页
    for pg in range(1, 6):
        rows, count = fetch_cninfo(pg, 50)
        new_rows.extend(rows)
        logger.info(f"CNINFO page {pg}: got {len(rows)} rows")
        if count < 50: break
        time.sleep(random.uniform(0.5, 1.0))

    # 2. 上交所随机抽 20 只
    sse_map = load_sse_map()
    if sse_map:
        samples = random.sample(list(sse_map.items()), min(20, len(sse_map)))
        for code, uid in samples:
            rows = fetch_sse_qa(code, uid, 10)
            new_rows.extend(rows)
            logger.info(f"SSE {code}: got {len(rows)} rows")
            time.sleep(random.uniform(0.3, 0.6))

    logger.info(f"Total new rows this run: {len(new_rows)}")
    return new_rows


def merge_and_save(new_rows):
    """合并去重并保存"""
    os.makedirs(DATA_DIR, exist_ok=True)
    qa_file = os.path.join(DATA_DIR, "all_qa.json")

    # Load existing
    existing = []
    if os.path.exists(qa_file):
        with open(qa_file, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # Merge by id
    by_id = {r["id"]: r for r in existing}
    added = 0
    for r in new_rows:
        if r["id"] not in by_id:
            added += 1
        by_id[r["id"]] = r

    all_data = list(by_id.values())
    all_data.sort(key=lambda x: x.get("pub_date", ""), reverse=True)

    # Save all_qa.json
    with open(qa_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=1)
    logger.info(f"Saved {len(all_data)} total QAs (+{added} new)")

    # Generate hot.json (top 20 by count in last 30 days)
    from collections import Counter
    stock_counts = Counter()
    stock_names = {}
    stock_sources = {}
    for r in all_data:
        c = r["stock_code"]
        stock_counts[c] += 1
        if r.get("stock_name"): stock_names[c] = r["stock_name"]
        if r.get("source"): stock_sources[c] = r["source"]

    hot = [{"stock_code": c, "stock_name": stock_names.get(c, c),
            "qa_count": n, "source": stock_sources.get(c, "")}
           for c, n in stock_counts.most_common(20)]
    with open(os.path.join(DATA_DIR, "hot.json"), "w", encoding="utf-8") as f:
        json.dump(hot, f, ensure_ascii=False, indent=1)

    # Generate stats.json
    stocks = set(r["stock_code"] for r in all_data)
    stats = {
        "total_records": len(all_data),
        "total_stocks": len(stocks),
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(DATA_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)

    logger.info(f"Generated hot.json ({len(hot)} stocks) and stats.json")
    return added


if __name__ == "__main__":
    logger.info("=== A股董秘说 GitHub Actions Scraper ===")
    new_rows = scrape_all()
    added = merge_and_save(new_rows)
    logger.info(f"Done! Added {added} new records.")
