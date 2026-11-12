"""Суточные рапорты бурения 16A(78)-32 (PDF WellEz) -> таблицы операций и долот.

Баланс времени разбирается по координатам слов: колонки FROM, TO, HRS, PHASE, CODE, NPT, OPERATIONS.
У одной даты бывает несколько версий рапорта — берём последнюю по номеру рапорта.
-> data/ops.parquet (операции), data/bits.parquet (отработка долот), data/days.parquet (сутки: забой, проходка, раствор)
"""
import re
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "reports" / "drilling"
TIME = re.compile(r"^\d{2}:\d{2}$")


def num(s):
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def parse(path):
    with pdfplumber.open(path) as pdf:
        words = [dict(w, page=i) for i, pg in enumerate(pdf.pages) for w in pg.extract_words()]
        text = "\n".join(pg.extract_text() or "" for pg in pdf.pages)
    m = re.search(r"RPT DATE:\s*(\d{1,2}/\d{1,2}/\d{4})", text)
    rpt = re.search(r"RPT NUM\.?:\s*(\d+)", text)
    if not m:
        return None
    date = pd.to_datetime(m[1])
    head = {"date": date, "rpt": int(rpt[1]) if rpt else None, "file": path.name}
    for key, rx in [("job", r"JOB:\s*(.+?)\s{2,}"), ("present", r"PRESENT OPERATIONS:\s*(.+)"), ("dfs", r"DFS:\s*(\d+)"),
                    ("hrs_drlg", r"HRS DRLG:\s*([\d.]+)"), ("ftg", r"24 HR FTG:\s*([\d,.]+)"), ("md_tvd", r"MD/TVD:\s*([\d,]+)")]:
        mm = re.search(rx, text)
        head[key] = mm[1].strip() if mm else None
    mw = re.search(r"\n\s*(\d{1,2}:\d{2})\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", text[text.find("MUD"):text.find("MUD") + 600]) if "MUD" in text else None
    head["mw_ppg"] = float(mw[2]) if mw else None
    # долота: строки таблицы DRILL BITS
    bits = []
    seg = text[text.find("DRILL BITS"):text.find("BIT NO.")] if "DRILL BITS" in text else ""
    for line in seg.split("\n")[2:]:
        t = line.split()
        if len(t) >= 6 and t[0].isdigit() and re.match(r"\d+(\.\d+)?$", t[1]):
            nums = [num(x) for x in t if num(x) is not None]
            bits.append({"date": date, "bit_no": int(t[0]), "size": float(t[1]), "raw": line.strip(), "nums": nums})
    # баланс времени: границы колонок — по заголовку таблицы на странице (FROM TO HRS PHASE CODE NPT OPERATIONS)
    ops = []
    cols = None
    for pg in sorted({w["page"] for w in words}):
        w = [x for x in words if x["page"] == pg]
        hdr = [x for x in w if x["text"] == "FROM"]
        top0 = -1
        if hdr:
            top0 = hdr[0]["top"]
            line = {x["text"]: x for x in w if abs(x["top"] - top0) < 2}
            if all(k in line for k in ("TO", "HRS", "PHASE", "CODE", "NPT", "OPERATIONS")):
                xs = {k: line[k]["x0"] for k in ("FROM", "TO", "HRS", "PHASE", "CODE", "NPT", "OPERATIONS")}
                cols = {"to": ((xs["FROM"] + xs["TO"]) / 2 + 4, (xs["TO"] + xs["HRS"]) / 2 + 2),
                        "hrs": ((xs["TO"] + xs["HRS"]) / 2 + 2, xs["HRS"] + 22),
                        "phase": (xs["HRS"] + 22, xs["CODE"] - 6), "code": (xs["CODE"] - 6, xs["NPT"] - 5),
                        "npt": (xs["NPT"] - 5, xs["OPERATIONS"] - 114.5), "text": (xs["OPERATIONS"] - 114.5, 5000), "from": (0, (xs["FROM"] + xs["TO"]) / 2 + 4)}
        if cols is None:
            continue
        end_y = min([x["top"] for x in w if x["text"] == "TOTAL" and x["x0"] < 200 and x["top"] > top0] or [1e9])
        # левая граница текста операций: самая частая позиция первого слова строки правее колонки «код»
        from collections import Counter
        lines = {}
        for x in w:
            if top0 < x["top"] < end_y and x["x0"] >= cols["npt"][0]:
                k = round(x["top"])
                lines[k] = min(lines.get(k, 1e9), x["x0"])
        if lines:
            margin = Counter(round(v) for v in lines.values()).most_common(1)[0][0] - 1
            cols["npt"] = (cols["npt"][0], margin)
            cols["text"] = (margin, 5000)
        starts = sorted([x for x in w if TIME.match(x["text"]) and cols["from"][0] <= x["x0"] < cols["from"][1] and top0 < x["top"] < end_y],
                        key=lambda x: x["top"])
        for i, s in enumerate(starts):
            y1 = starts[i + 1]["top"] if i + 1 < len(starts) else end_y
            blk = [x for x in w if s["top"] - 1 <= x["top"] < y1 - 0.5]
            line0 = [x for x in blk if abs(x["top"] - s["top"]) < 2]
            to = next((x["text"] for x in line0 if TIME.match(x["text"]) and cols["to"][0] <= x["x0"] < cols["to"][1]), None)
            hrs = next((num(x["text"]) for x in line0 if cols["hrs"][0] <= x["x0"] < cols["hrs"][1] and num(x["text"]) is not None), None)
            col = lambda k: " ".join(x["text"] for x in sorted(blk, key=lambda x: (round(x["top"]), x["x0"])) if cols[k][0] <= x["x0"] < cols[k][1])
            ops.append({"date": date, "from": s["text"], "to": to, "hrs": hrs, "phase": col("phase"), "code": col("code"),
                        "npt": col("npt"), "text": col("text")})
    return head, bits, ops


CODES = ["Rig Up & Tear Down", "Run Csg & Cement", "Cond Mud & Circ", "Cut off Drill Line", "Wire Line Logs", "Nipple Up B.O.P.", "Test B.O.P.",
         "Wait on Cement", "Lubricate Rig", "Repair Rig", "Rig Service", "Dir Work", "Reaming", "Coring", "Fishing", "Trips", "Drilling", "Other"]


def split_code(phase, code):
    """Фаза и код в рапорте разбиты по строкам ячейки: склеиваем и находим код по справочнику кодов WellEz."""
    full = re.sub(r"\s+", " ", f"{phase} {code}").strip()
    for c in CODES:
        words = c.split()
        # код может быть обрезан в конце ячейки («Cond Mud &», «Cut off Drill»): ищем по первым двум словам
        for k in (len(words), 2, 1):
            stem = " ".join(words[:k])
            i = full.rfind(stem)
            if i >= 0 and (k == len(words) or len(words) > 1) and (k > 1 or c in ("Trips", "Drilling", "Other", "Reaming", "Coring", "Fishing")):
                ph = full[:i].strip()
                if c == "Drilling" and not ph:
                    continue
                return ph, c
    return full, ""


def main():
    heads, bits, ops = [], [], []
    for f in sorted(RAW.glob("*.pdf")):
        r = parse(f)
        if r is None:
            continue
        h, b, o = r
        heads.append(h); bits += [dict(x, rpt=h["rpt"]) for x in b]; ops += [dict(x, rpt=h["rpt"]) for x in o]
    H = pd.DataFrame(heads).sort_values(["date", "rpt"])
    keep = H.groupby("date").rpt.max()
    H = H[H.rpt == H.date.map(keep)].drop_duplicates("date")
    O = pd.DataFrame(ops)
    O = O[O.rpt == O.date.map(keep)].drop_duplicates(["date", "from", "to", "text"])
    pc = [split_code(p_, c_) for p_, c_ in zip(O.phase, O.code)]
    O["phase"], O["code"] = [a for a, _ in pc], [b for _, b in pc]
    B = pd.DataFrame(bits)
    B = B[B.rpt == B.date.map(keep)]
    (ROOT / "data").mkdir(exist_ok=True)
    H.to_parquet(ROOT / "data/days.parquet", index=False)
    O.to_parquet(ROOT / "data/ops.parquet", index=False)
    B.drop(columns="nums").assign(nums=B.nums.map(lambda v: ",".join(map(str, v)))).to_parquet(ROOT / "data/bits.parquet", index=False)
    print("суток", len(H), H.date.min().date(), H.date.max().date(), "операций", len(O), "часов", O.hrs.sum())
    print(O.groupby(["phase"]).hrs.sum().sort_values(ascending=False).to_string())
    print(O.groupby(["code"]).hrs.sum().sort_values(ascending=False).head(40).to_string())
    print(O.groupby(["npt"]).hrs.sum().sort_values(ascending=False).to_string())
    bad = O.groupby("date").hrs.sum(); print("сутки не 24 ч:", bad[(bad - 24).abs() > 0.3].to_dict())


if __name__ == "__main__":
    main()
