"""壽險公會「壽險業績統計」PDF 解析：初年度保費依險別、依通路（含非保險合約／保費收入+負債口徑，單位百萬元）。"""
import re, subprocess, os, json, requests

SUFFIX = r"（(?:保費收入[+＋]負債|含非保險合約)）"
FYP_KEYS = ["life_trad", "life_inv", "life_sub", "acc", "health", "ann_trad", "ann_inv", "ann_sub", "tot_trad", "tot_inv", "tot"]
NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")

def nums(s):
    return [float(x.replace(",", "")) for x in NUM.findall(s)]

def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout

def period_of(text):
    head = " ".join(text.split("\n")[:6])
    m = re.search(r"(\d{2,3})\s*年\s*(\d{1,2})\s*~\s*(\d{1,2})\s*月", head)
    if m:
        return int(m.group(1)) + 1911, int(m.group(3))
    m = re.search(r"(\d{2,3})\s*年\s*(\d{1,2})\s*月", head)
    if m:
        return int(m.group(1)) + 1911, int(m.group(2))
    m = re.search(r"(\d{2,3})\s*年度", head)
    if m:
        return int(m.group(1)) + 1911, 12
    return None

def parse_fyp(lines):
    for i, l in enumerate(lines):
        if re.search(r"各險別初年度保費收入統計表", l) and re.search(SUFFIX, l):
            j = i + 1
            while j < len(lines) and "成長率" not in lines[j]:
                j += 1
            rows = []
            for l2 in lines[j + 1:j + 60]:
                if "成長率" in l2:
                    continue
                n = nums(l2)
                if len(n) >= 3:
                    rows.append(n[-3:])
                if len(rows) == 11:
                    break
            if len(rows) < 11:
                return None
            cur = dict(zip(FYP_KEYS, [r[0] for r in rows]))
            prev = dict(zip(FYP_KEYS, [r[1] for r in rows]))
            for d in (cur, prev):  # 勾稽
                ok = (abs(d["life_sub"] - d["life_trad"] - d["life_inv"]) <= 2
                      and abs(d["ann_sub"] - d["ann_trad"] - d["ann_inv"]) <= 2
                      and abs(d["tot_trad"] - d["life_trad"] - d["acc"] - d["health"] - d["ann_trad"]) <= 3
                      and abs(d["tot"] - d["tot_trad"] - d["tot_inv"]) <= 3)
                if not ok:
                    return None
            return cur, prev
    return None

CH_ROWS = [("total", r"^\s*保費收入"), ("life", r"個人壽險"), ("ann", r"個人年金"), ("inv", r"投資型保險"), ("ah", r"個人傷害")]
CH_NAMES = ["lia", "bank", "agent"]

def parse_channel(lines):
    for i, l in enumerate(lines):
        if re.search(r"初年度保費收入來源別統計表", l) and re.search(SUFFIX, l):
            got = {}
            for l2 in lines[i + 1:i + 40]:
                for key, rx in CH_ROWS:
                    if key not in got and re.search(rx, l2) and "比率" not in l2:
                        n = nums(l2)
                        if len(n) >= 4:
                            got[key] = n[-4:]
            if len(got) == 5:
                out = {}
                for ci, nm in enumerate(CH_NAMES):
                    out[nm] = {k: got[k][ci] for k in got}
                out["sum"] = {k: got[k][3] for k in got}
                t = got["total"]
                if abs(t[0] + t[1] + t[2] - t[3]) <= 3:
                    return out
            return None
    return None

def parse_report(text):
    p = period_of(text)
    if not p:
        return None
    lines = text.split("\n")
    f = parse_fyp(lines)
    c = parse_channel(lines)
    if not f:
        return None
    return {"year": p[0], "month": p[1], "cur": f[0], "prev": f[1], "ch": c}

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def download_text(url, tmp):
    r = requests.get(url, headers=UA, timeout=90)
    r.raise_for_status()
    open(tmp, "wb").write(r.content)
    t = pdf_text(tmp)
    os.remove(tmp)
    return t

def find_latest_url():
    from bs4 import BeautifulSoup
    u = "https://www.lia-roc.org.tw?catg_id=10&temp_menu_title=%E5%A3%BD%E9%9A%AA%E7%B5%B1%E8%A8%88%E8%B3%87%E6%96%99"
    s = BeautifulSoup(requests.get(u, headers=UA, timeout=60).text, "html.parser")
    for a in s.find_all("a", href=True):
        if "壽險業業績統計" in a.get_text() and "uploads" in a["href"]:
            return a["href"]
    return None

if __name__ == "__main__":  # 本機測試：python lia.py file.txt ...
    import sys
    for f in sys.argv[1:]:
        r = parse_report(open(f, encoding="utf-8").read())
        print(os.path.basename(f), None if not r else (r["year"], r["month"], r["cur"]["tot_inv"], r["cur"]["tot"], bool(r["ch"]), r["ch"] and r["ch"]["sum"]["total"]))
