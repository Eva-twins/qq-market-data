#!/usr/bin/env python3
"""每日更新：保發中心(投資型初年度保費/帳戶價值) + 投信投顧公會(類全委規模)。
輸出 data/ins.json、data/mk.json。解析規則與平台『手動匯入』完全一致。"""
import json, os, re, sys, time, datetime
import requests
from bs4 import BeautifulSoup
import xlrd

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

# ---------- 保發中心 ----------
def fetch_xls(name):
    r = requests.get(f"https://pivot.tii.org.tw/lifesta/{name}.xls", headers=UA, timeout=90)
    r.raise_for_status()
    wb = xlrd.open_workbook(file_contents=r.content)
    s = wb.sheet_by_index(0)
    return [s.row_values(i) for i in range(s.nrows)]

def parse_pivot(rows, cols, div):
    """列：年度(第0欄，只在每年第一列出現)、月份(第1欄)。與平台 insImport 相同。"""
    out, yr = {}, None
    for r in rows:
        a = str(r[0]).strip() if r[0] != "" else ""
        if re.fullmatch(r"\d{4}(\.0)?", a):
            yr = a[:4]
        m = str(r[1]).strip() if r[1] != "" else ""
        if m.endswith(".0"): m = m[:-2]
        if not yr or not re.fullmatch(r"\d{1,2}", m):
            continue
        try:
            v = [float(r[j]) for j in cols]
        except (ValueError, IndexError):
            continue
        out[f"{yr}-{m.zfill(2)}"] = [round(x / div, 1) for x in v]
    return out

def update_ins():
    prm = parse_pivot(fetch_xls("xPivoMonInvPrm1"), [8, 11, 14], 1e5)
    bif = parse_pivot(fetch_xls("xPivoMonInvBif1"), [7, 9, 11], 1e4)
    if len(prm) < 24 or len(bif) < 24:
        raise SystemExit(f"保發中心解析異常：prm={len(prm)} bif={len(bif)}")
    old = load("ins.json", {})
    save("ins.json", {"updated": NOW, "prm": prm, "bif": bif})
    print("ins: prm", len(prm), "bif", len(bif), "latest", max(prm), max(bif),
          "(changed)" if (old.get("prm"), old.get("bif")) != (prm, bif) else "(no change)")

# ---------- 投信投顧公會 ----------
URL = "https://www.sitca.org.tw/ROC/Industry/IN4001.aspx?pid=IN2211_04"
SEL = "ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolder1$ddlYYYYMM"

def hidden(soup):
    return {i["name"]: i.get("value", "") for i in soup.find_all("input", type="hidden") if i.get("name")}

def num(x):
    return float(x.replace(",", ""))

def parse_sitca(soup):
    t = soup.find(id=re.compile(r"TableMEMA1$"))
    if t is None:
        return None
    rows, tot = {}, None
    for tr in t.find_all("tr"):
        c = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(c) >= 8 and re.fullmatch(r"A\d{4}", c[0]):
            twd, usd = num(c[5]) / 1e8, num(c[7]) / 1e8
            if twd or usd:
                rows[c[1]] = {"TWD": round(twd, 1), "USD": round(usd, 1)}
        elif c and c[0] == "合計" and len(c) >= 7:
            tot = {"TWD": round(num(c[-3]) / 1e8, 1), "USD": round(num(c[-1]) / 1e8, 1)}
    return {"rows": rows, "tot": tot} if len(rows) >= 5 and tot else None

def months_between(a, b):
    y, m = int(a[:4]), int(a[4:])
    while f"{y}{m:02d}" <= b:
        yield f"{y}{m:02d}"
        m += 1
        if m > 12: y, m = y + 1, 1

def update_mk(start="201512", refresh_last=3):
    s = requests.Session(); s.headers.update(UA)
    r = s.get(URL, timeout=90); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    sel = soup.find("select", attrs={"name": SEL})
    opts = [o["value"] for o in sel.find_all("option")]
    cur = next(o["value"] for o in sel.find_all("option") if o.get("selected"))
    latest = max(opts)
    old = load("mk.json", {"snaps": {}})
    snaps = old.get("snaps", {})
    want = list(months_between(start, latest))
    have = {k.replace("-", "") for k in snaps}
    todo = [m for m in want if m not in have or m in want[-refresh_last:]]
    print("sitca: page default", cur, "latest option", latest, "todo", len(todo))
    cache = {cur: parse_sitca(soup)}
    fails = []
    for m in todo:
        if m in cache:
            res = cache[m]
        else:
            form = hidden(soup); form["__EVENTTARGET"] = SEL; form["__EVENTARGUMENT"] = ""; form[SEL] = m
            ok = False
            for attempt in range(3):
                try:
                    r = s.post(URL, data=form, timeout=90); r.raise_for_status()
                    soup = BeautifulSoup(r.text, "html.parser"); ok = True; break
                except Exception as e:
                    time.sleep(3)
            if not ok:
                fails.append(m); continue
            res = parse_sitca(soup)
            time.sleep(0.7)
        if res is None:
            fails.append(m); continue
        snaps[f"{m[:4]}-{m[4:]}"] = res
    if len(snaps) < 3:
        raise SystemExit("投信投顧公會解析異常")
    save("mk.json", {"updated": NOW, "snaps": snaps})
    print("sitca: snaps", len(snaps), "latest", max(snaps), "fails", fails)

# ---------- 壽險公會業績統計 ----------
def update_lia():
    import tempfile
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import lia
    src = json.load(open(os.path.join(ROOT, "scripts", "lia_sources.json"), encoding="utf-8"))
    old = load("lia.json", {"periods": {}, "sources": []})
    periods, done = old.get("periods", {}), set(old.get("sources", []))
    ids = list(src["backfill"])
    try:
        u = lia.find_latest_url()
        if u:
            ids.append(re.search(r"([0-9a-f]{13})\.pdf", u).group(1))
        else:
            print("lia: 找不到最新報告連結（頁面可能改版）", file=sys.stderr)
    except Exception as e:
        print("lia: 取得最新連結失敗", e, file=sys.stderr)
    tmp = os.path.join(tempfile.gettempdir(), "lia.pdf")
    new, bad = 0, []
    for i in dict.fromkeys(ids):
        if i in done:
            continue
        try:
            r = lia.parse_report(lia.download_text(f"https://www.lia-roc.org.tw/storage/uploads/{i}.pdf", tmp))
        except Exception as e:
            r = None; print("lia: 下載/解析失敗", i, e, file=sys.stderr)
        if not r:
            bad.append(i); continue
        k = f"{r['year']}-{r['month']:02d}"
        periods[k] = {"cur": r["cur"], "prev": r["prev"], "ch": r["ch"], "src": i}
        done.add(i); new += 1
    seed = json.load(open(os.path.join(DATA, "lia_seed.json"), encoding="utf-8"))
    save("lia.json", {"updated": NOW, "periods": periods, "sources": sorted(done), "seed": seed})
    print("lia: periods", len(periods), "new", new, "bad", bad, "latest", max(periods) if periods else None)
    if not periods:
        raise SystemExit("壽險公會報告解析全部失敗")

if __name__ == "__main__":
    errs = []
    for fn in (update_ins, update_mk, update_lia):
        try: fn()
        except BaseException as e:
            errs.append(f"{fn.__name__}: {e}"); print("ERROR", fn.__name__, e, file=sys.stderr)
    if errs: sys.exit(1)
