# -*- coding: utf-8 -*-
# CoolPC 每日價格追蹤器 v8.0
# v8.0: 新增記憶體追蹤，顯卡+記憶體雙報表、頁頂互相跳轉
import urllib.request, urllib.error, re, os, sys, csv
import html as htmllib
from datetime import datetime, timezone, timedelta

TWT = timezone(timedelta(hours=8))   # 台灣時間

# ========== 可自行修改 ==========
WATCH_KEYWORDS = []   # 想特別標記的型號,例如 ['RTX 5070', 'DDR5-6000']
AUTO_OPEN_REPORT = True
# ================================

URL = 'https://www.coolpc.com.tw/evaluate.php'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'coolpc_vga_data')

BRANDS = ['華碩', '技嘉', '微星', 'ZOTAC', 'INNO3D', '藍寶石', '撼訊', '華擎', 'ACER', '麗臺',
          '金士頓', '美光', '芝奇', '海盜船', 'KLEVV', '十銓', 'UMAX', '威剛']

VGA_GROUPS = [
    ('RTX 5090', r'RTX\s?5090'), ('RTX 5080', r'RTX\s?5080'),
    ('RTX 5070 Ti', r'RTX\s?5070\s?Ti'), ('RTX 5070', r'RTX\s?5070'),
    ('RTX 5060 Ti', r'RTX\s?5060\s?Ti'), ('RTX 5060', r'RTX\s?5060'),
    ('RTX 5050', r'RTX\s?5050'), ('RTX 3060', r'RTX\s?3060'), ('RTX 3050', r'RTX\s?3050'),
    ('RTX PRO 6000', r'PRO\s?6000'), ('RTX PRO 5000', r'PRO\s?5000'),
    ('RTX PRO 4500', r'PRO\s?4500'), ('RTX PRO 4000', r'PRO\s?4000'),
    ('RTX PRO 2000', r'PRO\s?2000'),
    ('RTX 6000 Ada', r'RTX\s?6000'), ('RTX 4000 Ada', r'RTX\s?4000'), ('RTX 2000 Ada', r'RTX\s?2000'),
    ('RTX A1000', r'RTX\s?A1000'), ('RTX A400', r'RTX\s?A400'),
    ('RX 9070 XT', r'RX\s?9070\s?XT'), ('RX 9070 GRE', r'RX\s?9070\s?GRE'), ('RX 9070', r'RX\s?9070'),
    ('RX 9060 XT', r'RX\s?9060\s?XT'), ('RX 7650 GRE', r'RX\s?7650'),
    ('R9700 AI 卡', r'R9700'), ('ARC B580/B70', r'B580|B70'),
    ('GT 1030', r'GT\s?1030'), ('GT 730', r'GT\s?730|N730'), ('GT 710/210', r'GT\s?710|N210'),
]

RAM_GROUPS = [
    ('ECC/伺服器', r'ECC'),
    ('DDR5 筆電', r'(?=.*NB)(?=.*(?:DDR5|D5-\d))'),
    ('DDR5 桌上型', r'(?:DDR5|D5-\d)'),
    ('DDR4 筆電', r'(?=.*NB)(?=.*(?:DDR4|D4-\d))'),
    ('DDR4 桌上型', r'(?:DDR4|D4-\d)'),
    ('DDR3', r'DDR3'),
]

CATEGORIES = [
    {'key': 'vga', 'title': '顯示卡每日報價',
     'header_words': ('顯示卡', 'VGA'), 'match_any': True,
     'not_words': ('筆記型', '電競主機', '品牌小主機', 'AIO'),
     'fallback_id': '12',
     'exclude': ['支架', '支撐架', 'HOLDER', '千斤頂', 'AI BOX', '外接式'],
     'groups': VGA_GROUPS, 'report': 'vga_report.html'},
    {'key': 'ram', 'title': '記憶體每日報價',
     'header_words': ('記憶體', 'RAM'), 'match_any': False,
     'not_words': ('筆記型', '固態硬碟', '顯示卡'),
     'fallback_id': '6',
     'exclude': [],
     'groups': RAM_GROUPS, 'report': 'ram_report.html'},
]

def log(*a): print('[Tracker]', *a)

def norm_name(n):
    n = re.sub(r'▼.*$', '', n or '')
    return n.replace(' ', '').replace('\u3000', '').strip()

def fetch_html():
    log('下載原價屋估價頁中...')
    req = urllib.request.Request(URL, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=120) as r: raw = r.read()
    for enc in ('big5', 'big5-hkscs', 'utf-8'):
        try: return raw.decode(enc)
        except (UnicodeDecodeError, LookupError): pass
    return raw.decode('big5', errors='ignore')

def find_section(page, cat):
    pat = re.compile(r'<select\b[^>]*name\s*=\s*[\'"]?n(\d+)[^>]*>(.*?)</select>', re.I | re.S)
    fallback = None
    for m in pat.finditer(page):
        cid, body = m.group(1), m.group(2)
        pre = re.sub(r'<[^>]+>', ' ', page[max(0, m.start()-500):m.start()])
        ok = (any(w in pre for w in cat['header_words']) if cat['match_any']
              else all(w in pre for w in cat['header_words']))
        if ok and not any(w in pre for w in cat['not_words']):
            return body
        if cid == cat['fallback_id']: fallback = body
    return fallback

def parse_options(body, cat):
    items = []
    for m in re.finditer(r'<option\b([^>]*)>(.*?)</option>', body, re.I | re.S):
        attrs, raw = m.group(1), m.group(2)
        val = re.search(r'value\s*=\s*[\'"]?([^\'"\s>]+)', attrs, re.I)
        text = re.sub(r'<[^>]+>', '', raw)
        text = re.sub(r'\s+', ' ', htmllib.unescape(text)).strip()
        if '共有商品' in text: continue
        prices = [int(p.replace(',', '')) for p in re.findall(r'\$([0-9][0-9,]*)', text)]
        name = text.split('$')[0].strip().strip(',，').strip()
        if not prices or not name: continue
        if cat['key'] == 'vga' and ('吋' in name or '筆電' in name): continue
        low = name.lower()
        if any(k.lower() in low for k in cat['exclude']): continue
        items.append({'id': val.group(1) if val else '', 'name': name, 'price': prices[-1],
                      'raw': text, 'hot': '熱賣' in text})
    return items

def detect_group(name, groups):
    for label, pat in groups:
        if re.search(pat, name, re.I): return label
    return '其他'

def get_brand(name):
    for b in BRANDS:
        if name.startswith(b): return b
    return name.split(' ')[0]

CSS = """*{box-sizing:border-box;margin:0;padding:0}body{background:#14151a;color:#e8e8ec;font-family:'Microsoft JhengHei',sans-serif;padding:24px}h1{font-size:22px}h2{font-size:16px;margin:18px 0 10px;color:#8ab4ff}.nav{display:flex;gap:10px;margin:10px 0}.nav a{color:#8ab4ff;text-decoration:none;background:#1e2028;border:1px solid #2a2d37;padding:8px 18px;border-radius:8px;font-weight:700}.nav a.active{background:#8ab4ff;color:#14151a}.meta{color:#9aa0ab;margin:6px 0 14px;font-size:13px}.toolbar{display:flex;gap:14px;align-items:center;margin-bottom:18px;position:sticky;top:0;background:#14151a;padding:10px 0;z-index:9}#q{flex:1;max-width:420px;padding:10px 14px;border-radius:8px;border:1px solid #333;background:#1e2028;color:#eee;font-size:14px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}.card{background:#1e2028;border:1px solid #2a2d37;border-radius:10px;padding:12px}.card .chip{color:#8ab4ff;font-weight:700}.card .low{color:#ffd75e;font-size:18px;font-weight:800;margin:4px 0}.card .model{color:#9aa0ab;font-size:11px;line-height:1.5}details.group{margin-bottom:12px;border:1px solid #2a2d37;border-radius:10px;overflow:hidden}summary{cursor:pointer;background:#1e2028;padding:12px 16px;font-weight:700}summary .min{color:#ffd75e;margin-left:10px;font-size:13px}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:8px 12px;border-top:1px solid #23252e;text-align:left}thead th{color:#9aa0ab;background:#191b21}tbody tr:hover{background:#232530}.price{color:#ffd75e;font-weight:700;white-space:nowrap}.down{color:#5dd39e;font-weight:700}.up{color:#ff7b72;font-weight:700}.same{color:#565b66}.new{color:#8ab4ff;font-weight:700}tr.watch td:first-child{box-shadow:inset 3px 0 0 #ffd75e}@media (max-width:640px){body{padding:12px}td,th{padding:6px 8px;font-size:12px}td:nth-child(2){word-break:break-all}.card .low{font-size:16px}#q{max-width:none}}"""

JS = """function filterRows(){var q=document.getElementById('q').value.trim().toLowerCase();var oc=document.getElementById('onlyChanged').checked;document.querySelectorAll('.group').forEach(function(g){var v=0;g.querySelectorAll('tbody tr').forEach(function(tr){var okQ=!q||tr.dataset.name.toLowerCase().includes(q);var okC=!oc||tr.dataset.changed==='1';var s=okQ&&okC;tr.style.display=s?'':'none';if(s)v++;});g.style.display=v?'':'none';if(q&&v)g.open=true;});}"""

def build_report(cat, items, prev, prev_date, today, now):
    groups = {}
    for it in items: groups.setdefault(detect_group(it['name'], cat['groups']), []).append(it)
    order = [g[0] for g in cat['groups']] + ['其他']
    cards, groups_html = [], []
    gi = 0
    for label in order:
        g = groups.get(label)
        if not g: continue
        g.sort(key=lambda x: x['price'])
        low = g[0]
        cards.append(f'<div class="card"><div class="chip">{label}</div><div class="low">${low["price"]:,}</div><div class="model">{htmllib.escape(low["name"])}</div></div>')
        rows = []
        for it in g:
            old = prev.get(norm_name(it['name']))
            if old is None:
                chg = '<td class="new">新上架</td>' if prev else '<td class="same">—</td>'; changed = 0
            elif old != it['price']:
                d = it['price'] - old
                chg = f'<td class="down">▼ {abs(d):,}</td>' if d < 0 else f'<td class="up">▲ {d:,}</td>'; changed = 1
            else:
                chg = '<td class="same">—</td>'; changed = 0
            watch = ' class="watch"' if any(k.lower() in it['name'].lower() for k in WATCH_KEYWORDS) else ''
            rows.append(f'<tr data-name="{htmllib.escape(it["name"], quote=True)}" data-changed="{changed}"{watch}>'
                        f'<td>{get_brand(it["name"])}</td><td>{htmllib.escape(it["name"])}</td>'
                        f'<td class="price">${it["price"]:,}</td>{chg}</tr>')
        groups_html.append(
            f'<details class="group" {"open" if gi < 2 else ""}><summary>{label}（{len(g)} 款）'
            f'<span class="min">最低 ${low["price"]:,}</span></summary>'
            f'<table><thead><tr><th>品牌</th><th>型號</th><th>價格</th><th>較{prev_date or "上次"}</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></details>')
        gi += 1
    down = sum(1 for it in items if norm_name(it['name']) in prev and prev[norm_name(it['name'])] > it['price'])
    up = sum(1 for it in items if norm_name(it['name']) in prev and prev[norm_name(it['name'])] < it['price'])
    av = 'active' if cat['key'] == 'vga' else ''
    ar = 'active' if cat['key'] == 'ram' else ''
    return ('<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{cat["title"]} {today}</title><style>{CSS}</style></head><body>'
            f'<h1>{cat["title"]}</h1>'
            f'<div class="nav"><a href="index.html" class="{av}">🎮 顯示卡</a><a href="ram.html" class="{ar}">🧮 記憶體</a></div>'
            f'<div class="meta">日期：{today} {now.strftime("%H:%M")}｜共 {len(items)} 項｜'
            f'降價 {down} 項 ／ 漲價 {up} 項｜比較基準：{prev_date or "無(首日)"}</div>'
            f'<div class="toolbar"><input id="q" placeholder="🔍 搜尋品牌/型號，例如：金士頓、DDR5、芝奇..." oninput="filterRows()">'
            '<label><input type="checkbox" id="onlyChanged" onchange="filterRows()"> 只看價格異動</label></div>'
            '<h2>💡 各分組最低價</h2><div class="cards">' + ''.join(cards) + '</div>'
            '<h2>📋 分組明細（點標題展開）</h2>' + ''.join(groups_html) + f'<script>{JS}</script></body></html>')

def process_category(cat, page, today, now):
    log(f'--- 處理 {cat["title"]} ---')
    body = find_section(page, cat)
    if not body: log('找不到分類，跳過'); return
    items = parse_options(body, cat)
    log(f'共解析到 {len(items)} 項')
    if not items: return

    prev, prev_date = {}, None
    cand = sorted((f, m.group(1)) for f in os.listdir(DATA_DIR)
                  if (m := re.match(cat['key'] + r'_(\d{4}-\d{2}-\d{2})\.csv$', f)) and m.group(1) < today)
    if cand:
        prev_date = cand[-1][1]
        with open(os.path.join(DATA_DIR, cand[-1][0]), newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                try: prev[norm_name(row['產品名稱'])] = int(row['目前價格'])
                except Exception: pass

    with open(os.path.join(DATA_DIR, f'{cat["key"]}_{today}.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['產品ID', '產品名稱', '目前價格', '熱賣', '原始文字'])
        for it in items: w.writerow([it['id'], it['name'], it['price'], '是' if it['hot'] else '', it['raw']])

    hist = os.path.join(DATA_DIR, f'{cat["key"]}_history.csv')
    newf = not os.path.exists(hist)
    with open(hist, 'a', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        if newf: w.writerow(['日期', '時間', '產品ID', '產品名稱', '目前價格'])
        for it in items: w.writerow([today, now.strftime('%H:%M'), it['id'], it['name'], it['price']])

    report_html = build_report(cat, items, prev, prev_date, today, now)
    report_path = os.path.join(BASE_DIR, cat['report'])
    with open(report_path, 'w', encoding='utf-8') as f: f.write(report_html)
    log(f'報表已產生: {report_path}')

    if prev:
        ch = [it for it in items if norm_name(it['name']) in prev and prev[norm_name(it['name'])] != it['price']]
        log(f'與 {prev_date} 相比: 異動 {len(ch)} 項')

def main():
    now = datetime.now(TWT); today = now.strftime('%Y-%m-%d')
    os.makedirs(DATA_DIR, exist_ok=True)
    page = fetch_html()
    for cat in CATEGORIES:
        process_category(cat, page, today, now)
    if AUTO_OPEN_REPORT and '--quiet' not in sys.argv:
        try: os.startfile(os.path.join(BASE_DIR, 'vga_report.html'))
        except Exception: pass

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('[嚴重錯誤]', e); sys.exit(1)
