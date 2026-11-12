"""Презентация: slides.html и PDF (Chromium из Playwright). Запуск: uv run --with playwright python presentation/build_slides.py"""
import base64
import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIG, OUT = ROOT / "reports" / "figures", ROOT / "out"
CSS = (Path.home() / "Дядя Грэвел/Аналитика ДГ/rvvr/presentation/slides.css.txt").read_text(encoding="utf-8")
EXTRA = """<style>
:root { --accent: #e8590c; }
.verdict { background: var(--ink); }
.one { display: grid; grid-template-rows: 1fr auto; gap: 16px; min-height: 0; }
.one img { width: 100%; max-height: 440px; object-fit: contain; background: #fcfcfb; border: 1px solid var(--line); border-radius: 10px; padding: 8px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
.vec { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px 18px; }
.vec b { display: block; font-family: var(--f-display); font-size: 22px; text-transform: uppercase; margin-bottom: 4px; }
.vec p { font-size: 15.5px; }
.num { color: var(--accent); }
</style>"""
r = json.load(open(OUT / "results.json"))
g = json.load(open(OUT / "geomech.json"))


def img(name):
    return "data:image/png;base64," + base64.b64encode((FIG / f"{name}.png").read_bytes()).decode()


def fmt(x, d=0):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


slides, k = [], [0]


def slide(eyebrow, title, body):
    k[0] += 1
    slides.append(f'<section class="slide"><div><div class="eyebrow">{eyebrow}</div><h2>{title}</h2></div>{body}'
                  f'<div class="foot"><span>Utah FORGE 16A(78)-32 · коммерческая скорость, MSE, геомеханика</span><span>{k[0]}</span></div></section>')


def chart(eyebrow, title, fig, verdict):
    slide(eyebrow, title, f'<div class="one"><img src="{img(fig)}"><div class="verdict">{verdict}</div></div>')


a, p, pot = r["actual"], r["production_like"], r["potential"]
slides.append(f'''<section class="slide" style="grid-template-rows:1fr auto"><div style="align-self:center">
<div class="eyebrow">Разбор строительства скважины · открытые данные Utah FORGE</div><h1>Где были сутки:<br>скорость, MSE<br><span class="num">и геомеханика</span></h1></div>
<div class="kpis"><div class="kpi"><div class="v">3 349 м</div><div class="l">по стволу, тангенс 65° в граните</div></div>
<div class="kpi"><div class="v">{fmt(a['days'], 1)} сут</div><div class="l">от забуривания до хвостовика</div></div>
<div class="kpi"><div class="v">{fmt(a['comm_speed'])}</div><div class="l">м/ст.-мес. факт</div></div>
<div class="kpi"><div class="v">{fmt(pot['comm_speed'])}</div><div class="l">м/ст.-мес. потенциал</div></div></div></section>''')
k[0] = 1
chart("Итог", f"+10% к коммерческой скорости без новых технологий", "09_waterfall",
      f"Без программы исследований скважина шла бы {fmt(p['days'], 1)} сут. Пять организационных мероприятий дают ещё {fmt(pot['save_days'], 1)} сут: "
      f"<b>{fmt(pot['days'], 1)} сут и {fmt(pot['comm_speed'])} м/ст.-мес.</b>")
chart("Баланс времени", "СПО заняли больше, чем бурение", "01_balance",
      "15,2 сут на СПО и смену КНБК против 13,9 сут бурения. НПВ — 2,6 сут. Резерв — в рейсах, а не в аварийности.")
chart("Механическая скорость", "В тангенсе — в 1,5 раза быстрее при той же прочности", "04_rop_ucs",
      f"Нагрузку снизили с {fmt(r['rop']['early_wob'] * .4536, 1)} до {fmt(r['rop']['late_wob'] * .4536, 1)} т, обороты ротора подняли с {fmt(r['rop']['early_td_rpm'])} до {fmt(r['rop']['late_td_rpm'])}. "
      "Для PDC в граните — режим с первого рейса.")
chart("MSE", "Долото работало нормально, энергия терялась на трение", "06_mse",
      "MSE на долоте ≈ 2,7 UCS, КПД около 37% — рабочий уровень. Рост MSE по поверхности — момент на трение колонны в наклонном стволе.")
chart("Отработка долот", "Рейс №14 бурили изношенным долотом лишние сутки", "05_bit14",
      "Подъём по минимуму времени на метр с учётом СПО — после 51 м. Остальные рейсы подняли до износа: керн, смена КНБК, температура.")
chart("Наращивания", "Бригада быстрая, теряется время вокруг клиньев", "07_connections",
      "В клиньях 3 мин, от нагрузки до нагрузки 12,5. Регламент 9 мин — минус 19 ч на скважину.")
chart("Геомеханика", "Ствол устойчив, окно плотности широкое", "08_geomech",
      f"UCS {fmt(g['ucs_mpa_med'])} МПа, {fmt(g['in_gauge'] * 100)}% ствола в номинале, раствор на уровне порового давления. Потери времени — не геомеханические.")
vec = [("1. Режим PDC в граните", "Меньше нагрузка, выше обороты, контроль MSE на долоте внутри рейса."),
       ("2. Отработка по времени на метр", "Подъём, когда текущее время на метр выше среднего с учётом СПО."),
       ("3. Длиннее рейсы", "Цель — 200+ м на рейс, как у трёх лучших: 9 рейсов вместо 13, минус 1,7 сут."),
       ("4. Наращивания по регламенту", "Проработка и замер в 9 мин, отчёт «от нагрузки до нагрузки» по вахтам."),
       ("5. ППР до забуривания", "Буровой насос, верхний привод, захват: их ремонт — 40% НПВ."),
       ("Данные и код", "Рапорты, станция 10 с, каротаж Schlumberger. Открытые данные GDR, код на GitHub.")]
slide("Что делать", "Пять мероприятий", '<div class="cols">' + "".join(f'<div class="vec"><b>{t}</b><p>{x}</p></div>' for t, x in vec) + "</div>")
html = f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Utah FORGE 16A: коммерческая скорость</title>{CSS}{EXTRA}</head><body>{"".join(slides)}</body></html>'
out = Path(__file__).with_name("slides.html")
out.write_text(html, encoding="utf-8")
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    exe = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/*/*/chrome-headless-shell")))
    br = pw.chromium.launch(executable_path=exe[-1]) if exe else pw.chromium.launch()
    pg = br.new_page(); pg.goto(out.as_uri()); pg.wait_for_timeout(800)
    pg.pdf(path=str(Path(__file__).with_name("Presentation_FORGE_16A.pdf")), width="1280px", height="720px", print_background=True)
    br.close()
print("ok", len(slides))
