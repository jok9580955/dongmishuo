import sqlite3
import json
import os
from datetime import datetime
from collections import Counter

DB_PATH = "../backend/dongmi.db"
DATA_DIR = "data"
QA_FILE = os.path.join(DATA_DIR, "all_qa.json")

def export():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM interactions ORDER BY pub_date DESC")
    rows = c.fetchall()
    
    data = []
    for r in rows:
        data.append({
            "id": r["id"],
            "stock_code": r["stock_code"],
            "stock_name": r["stock_name"],
            "question": r["question"],
            "answer": r["answer"],
            "pub_date": r["pub_date"],
            "reply_date": r["reply_date"],
            "source": r["source"],
            "url": r["url"]
        })
    
    # Save all_qa.json
    with open(QA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    
    print(f"Exported {len(data)} records to {QA_FILE}")
    
    # Generate hot.json (top 20 by count)
    stock_counts = Counter()
    stock_names = {}
    stock_sources = {}
    for r in data:
        c = r["stock_code"]
        stock_counts[c] += 1
        if r.get("stock_name"): stock_names[c] = r["stock_name"]
        if r.get("source"): stock_sources[c] = r["source"]

    hot = [{"stock_code": c, "stock_name": stock_names.get(c, c),
            "qa_count": n, "source": stock_sources.get(c, "")}
           for c, n in stock_counts.most_common(20)]
    with open(os.path.join(DATA_DIR, "hot.json"), "w", encoding="utf-8") as f:
        json.dump(hot, f, ensure_ascii=False, indent=1)
    print(f"Exported {len(hot)} hot stocks to hot.json")

    # Generate stats.json
    stocks = set(r["stock_code"] for r in data)
    stats = {
        "total_records": len(data),
        "total_stocks": len(stocks),
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(DATA_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print("Exported stats.json")
    
    conn.close()

if __name__ == "__main__":
    export()
