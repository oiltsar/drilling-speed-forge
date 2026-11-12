"""Баланс календарного времени 16A(78)-32 по суточным рапортам: виды работ, исследования программы FORGE, НПВ.

Коды WellEz укрупнены в виды работ, а операции «прочее», «промывка» и СПО разнесены по тексту: что относится к
программе исследований FORGE (керн, ГИС, температурные замеры, испытания на приёмистость, пакеры, гироскоп), что — к
НПВ (ремонт, отказы, промыв труб), что — к обычной проводке скважины. Это нужно, чтобы отделить скорость бурения от
научной программы: у производственной скважины исследований такого объёма не будет.
-> data/balance.parquet, out/balance_by_kind.csv
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCIENCE = re.compile(r"\bcor(e|ing)\b|core bha|wire ?line|logs?\b|logging|schlumberger|temperature build|build up (survey|test)|bottom hole temp|"
                     r"leak ?off|dfit|step rate|packer|gyro|string shot|acoustic|extreme wireline|survey tool|sanvean|step-rate|injection test|"
                     r"for logs|cool(ing)? bha|cooling bha", re.I)
COOL = re.compile(r"temperature|cool", re.I)
NPT = re.compile(r"fail|wash ?out|check for washes|stator|repair|broke(n)?\b|lost (pieces|circulation|\d+ stand ?pipe)|fish|mill(ed)? up|stuck|"
                 r"pipe free|work pipe|high winds|did not|attempted", re.I)
WAIT = re.compile(r"wait(ing)? on (?!cement)|standby|no activity", re.I)


def kind(code, phase, text):
    t = str(text)
    if phase == "Move In" or code == "Rig Up & Tear Down":
        return "Монтаж и подготовка"
    if code == "Repair Rig" or code == "Fishing":
        return "НПВ: ремонт и аварии"
    if code in ("Run Csg & Cement", "Wait on Cement", "Nipple Up B.O.P.", "Test B.O.P.") or phase == "Casing" or re.search(r"wellhead|casing|liner|cement", t, re.I) and code == "Other":
        return "Крепление и ПВО"
    if code in ("Wire Line Logs", "Coring"):
        return "Исследования FORGE"
    if code == "Drilling":
        if SCIENCE.search(t) and not re.search(r"drill (ahead|from|curve|tangent)", t, re.I):
            return "Исследования FORGE"
        return "Бурение"
    if code == "Reaming":
        return "Проработка"
    if code == "Cond Mud & Circ":
        if SCIENCE.search(t):
            return "Исследования FORGE"
        if NPT.search(t):
            return "НПВ: ремонт и аварии"
        return "Промывка и охлаждение" if COOL.search(t) else "Промывка и охлаждение"
    if code == "Trips":
        if SCIENCE.search(t):
            return "Исследования FORGE"
        if NPT.search(t):
            return "НПВ: ремонт и аварии"
        return "СПО и смена КНБК"
    if code == "Dir Work":
        return "СПО и смена КНБК"
    if code in ("Rig Service", "Lubricate Rig", "Cut off Drill Line"):
        return "Обслуживание станка"
    # «прочее» и пустой код
    if SCIENCE.search(t):
        return "Исследования FORGE"
    if NPT.search(t) or WAIT.search(t):
        return "НПВ: ремонт и аварии"
    if re.search(r"\bdrill(ing)? (ahead|from|curve)", t, re.I):
        return "Бурение"
    if re.search(r"bha|trip", t, re.I):
        return "СПО и смена КНБК"
    return "Прочее"


def main():
    o = pd.read_parquet(ROOT / "data/ops.parquet")
    o["kind"] = [kind(c, p, t) for c, p, t in zip(o.code, o.phase, o.text)]
    spud = pd.Timestamp("2020-10-30")
    o["stage"] = "после забуривания"
    o.loc[o.date < spud, "stage"] = "до забуривания"
    o.to_parquet(ROOT / "data/balance.parquet", index=False)
    (ROOT / "out").mkdir(exist_ok=True)
    b = o[o.stage == "после забуривания"].groupby("kind").hrs.sum().sort_values(ascending=False)
    tot = b.sum()
    out = pd.DataFrame({"часов": b, "суток": (b / 24).round(1), "доля": (b / tot).round(3)})
    out.to_csv(ROOT / "out/balance_by_kind.csv")
    print(out.to_string(), "\nвсего суток", round(tot / 24, 1), "от", o[o.stage == "после забуривания"].date.min().date(), "до", o.date.max().date())
    for k in ["НПВ: ремонт и аварии", "Прочее"]:
        print("====", k)
        for _, r in o[o.kind == k].sort_values("hrs", ascending=False).head(20).iterrows():
            print(f"{r.date.date()} {r.hrs:5} {r.code:18} | {r.text[:140]}")


if __name__ == "__main__":
    main()
