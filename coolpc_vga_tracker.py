# -*- coding: utf-8 -*-
# CoolPC 顯示卡每日價格追蹤器 v6.0
# v6.0: 新增專業卡晶片分類(RTX A/Ada/PRO Blackwell) + 報表更名為「顯示卡每日報價」
import urllib.request, urllib.error, re, os, sys, csv
import html as htmllib, base64, json
from datetime import datetime

# ========== 可自行修改 ==========
WATCH_KEYWORDS = []   # 想特別標記的型號,例如 ['RTX 5070']
EXCLUDE_KEYWORDS = ['支架', '支撐架', 'HOLDER', '千斤頂', 'AI BOX', '外接式']
AUTO_OPEN_REPORT = True

# --- 手機固定連結同步（不用就留空）---
GITHUB_USER  = ''
GITHUB_REPO  = ''
GITHUB_TOKEN = ''
# ================================

URL = 'https://www.coolpc.com.tw/evaluate.php'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'coolpc_vga_data')

BRANDS = ['華碩', '技嘉', '微星', 'ZOTAC', 'INNO3D', '藍寶石', '撼訊', '華擎', 'ACER', '麗臺']
CHIPS = [
    # 遊戲卡
    ('RTX 5090', r'RTX\s?5090'), ('RTX 5080', r'RTX\s?5080'),
    ('RTX 5070 Ti', r'RTX\s?5070\s?Ti'), ('RTX 5070', r'RTX\s?5070'),
    ('RTX 5060 Ti', r'RTX\s?5060\s?Ti'), ('RTX 5060', r'RTX\s?5060'),
    ('RTX 5050', r'RTX\s?5050'), ('RTX 3060', r'RTX\s?3060'), ('RTX 3050', r'RTX\s?3050'),
    # 專業/工作站卡
    ('RTX PRO 6000', r'PRO\s?6000'), ('RTX PRO 5000', r'PRO\s?5000'),
    ('RTX PRO 4500', r'PRO\s?4500'), ('RTX PRO 4000', r'PRO\s?4000'),
    ('RTX PRO 2000', r'PRO\s?2000'),
    ('RTX 6000 Ada', r'RTX\s?6000'), ('RTX 4000 Ada', r'RTX\s?4000'), ('RTX 2000 Ada', r'RTX\s?2000'),
    ('RTX A1000', r'RTX\s?A1000'), ('RTX A400', r'RTX\s?A400'),
    # AMD / 其他
    ('RX 9070 XT', r'RX\s?9070\s?XT'), ('RX 9070 GRE', r'RX\s?9070\s?GRE'), ('RX 9070', r'RX\s?9070'),
    ('RX 9060 XT', r'RX\s?9060\s?XT'), ('RX 7650 GRE', r'RX\s?7650'),
    ('R9700 AI 卡', r'R9700'), ('ARC B580/B70', r'B580|B70'),
    ('GT 1030', r'GT\s?1030'), ('GT 730', r'GT\s?730|N730'), ('GT 710/210', r'GT\s?710|N210'),
]

def log(*a): print('[VGA Tracker]', *a)

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

def find_vga_section(page):
    pat = re.compile(r'<select\b[^>]*name\s*=\s*[\'"]?n(\d+)[^>]*>(.*?)</select>', re.I | re.S)
    fallback = None
    for m in pat.finditer(page):
        cid, body = m.group(1), m.group(2)
        pre = re.sub(r'<[^>]+>', ' ', page[max(0, m.start()-500):m.start()])
        if ('顯示卡' in pre or 'VGA' in pre) and not any(w in pre for w in ('筆記型', '電競主機', '品牌小主機', 'AIO')):
            return cid, body
        if cid == '12': fallback = body
    return ('12', fallback) if fallback else (None, None)

def parse_options(body):
    items = []
    for m in re.finditer(r'<option\b([^>]*)>(.*?)</option>', body, re.I | re.S):
        attrs, raw = m.group(1), m.group(2)
        val = re.search(r'value\s*=\s*[\'"]?([^\'"\s>]+)', attrs, re.I)
        text = re.sub(r'<[^>]+>', '', raw)
        text = re.sub(r'\s+', ' ', htmllib.unescape(text)).strip()
        if '共有商品' in text: continue
        prices = [int(p.replace(',', '')) for p in re.findall(r'\$([0-9][0-9,]*)', text)]
        name = text.split('$')[0].strip().strip(',，').strip()
        if not prices or not name or '吋' in name or '筆電' in name: continue
        if any(k.lower() in name.lower() for k in EXCLUDE_KEYWORDS): continue
        items.append({'id': val.group(1) if val else '', 'name': name, 'price': prices[-1],
                      'raw': text, 'hot': '熱賣' in text})
    return items

def detect_chip(name):
    for label, pat in CHIPS:
        if re.search(pat, name, re.I): return label
    return '其他'

def get_brand(name):
    for b in BRANDS:
        if name.startswith(b): return b
    return name.split(' ')[0]

CSS = """*{box-sizing:border-box;margin:0;padding:0}body{background:#14151a;color:#e8e8ec;font-family:'Microsoft JhengHei',sans-serif;padding:24px}h1{font-size:22px}h2{font-size:16px;margin:18px 0 10px;color:#8ab4ff}.meta{color:#9aa0ab;margin:6px 0 14px;font-size:13px}.toolbar{display:flex;gap:14px;align-items:center;margin-bottom:18px;position:sticky;top:0;background:#14151a;padding:10px 0;z-index:9}#q{flex:1;max-width:420px;padding:10px 14px;border-radius:8px;border:1px solid #333;background:#1e2028;color:#eee;font-size:14px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}.card{background:#1e2028;border:1px solid #2a2d37;border-radius:10px;padding:12px}.card .chip{color:#8ab4ff;font-weight:700}.card .low{color:#ffd75e;font-size:18px;font-weight:800;margin:4px 0}.card .model{color:#9aa0ab;font-size:11px;line-height:1.5}details.group{margin-bottom:12px;border:1px solid #2a2d37;border-radius:10px;overflow:hidden}summary{cursor:pointer;background:#1e2028;padding:12px 16px;font-weight:700}summary .min{color:#ffd75e;margin-left:10px;font-size:13px}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:8px 12px;border-top:1px solid #23252e;text-align:left}thead th{color:#9aa0ab;background:#191b21}tbody tr:hover{background:#232530}.price{color:#ffd75e;font-weight:700;white-space:nowrap}.down{color:#5dd39e;font-weight:700}.up{color:#ff7b72;font-weight:700}.same{color:#565b66}.new{color:#8ab4ff;font-weight:700}tr.watch td:first-child{box-shadow:inset 3px 0 0 #ffd75e}@media (max-width:640px){body{padding:12px}td,th{padding:6px 8px;font-size:12px}td:nth-child(2){word-break:break-all}.card .low{font-size:16px}#q{max-width:none}}"""

JS = """function filterRows(){var q=document.getElementById('q').value.trim().toLowerCase();var oc=document.getElementById('onlyChanged').checked;document.querySelectorAll('.group').forEach(function(g){var v=0;g.querySelectorAll('tbody tr').forEach(function(tr){var okQ=!q||tr.dataset.name.toLowerCase().includes(q);var okC=!oc||tr.dataset.changed==='1';var s=okQ&&okC;tr.style.display=s?'':'none';if(s)v++;});g.style.display=v?'':'none';if(q&&v)g.open=true;});}"""

def build_report(items, prev, prev_date, today, now):
    groups = {}
    for it in items: groups.setdefault(detect_chip(it['name']), []).append(it)
    order = [c[0] for c in CHIPS] + ['其他']
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
    return ('<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>顯示卡每日報價 {today}</title><style>{CSS}</style></head><body>'
            f'<h1>顯示卡每日報價</h1><div class="meta">日期：{today} {now.strftime("%H:%M")}｜共 {len(items)} 張顯卡｜'
            f'降價 {down} 項 ／ 漲價 {up} 項｜比較基準：{prev_date or "無(首日)"}</div>'
            f'<div class="toolbar"><input id="q" placeholder="🔍 搜尋品牌/型號，例如：華碩、5070、麗臺..." oninput="filterRows()">'
            '<label><input type="checkbox" id="onlyChanged" onchange="filterRows()"> 只看價格異動</label></div>'
            '<h2>💡 各晶片最低價</h2><div class="cards">' + ''.join(cards) + '</div>'
            '<h2>📋 分組明細（點標題展開）</h2>' + ''.join(groups_html) + f'<script>{JS}</script></body></html>')

def upload_github(html_text, today):
    if not (GITHUB_USER and GITHUB_REPO and GITHUB_TOKEN): return
    api = f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/docs/index.html'
    hdr = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github+json', 'User-Agent': UA}
    sha = None
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers=hdr), timeout=30) as r:
            sha = json.load(r).get('sha')
    except urllib.error.HTTPError as e:
        if e.code != 404:
            log('GitHub 上傳失敗:', e.code); return
    payload = {'message': f'VGA report {today}', 'content': base64.b64encode(html_text.encode('utf-8')).decode()}
    if sha: payload['sha'] = sha
    req = urllib.request.Request(api, data=json.dumps(payload).encode('utf-8'), headers=hdr, method='PUT')
    try:
        with urllib.request.urlopen(req, timeout=60):
            log(f'已上傳 GitHub! 手機連結: https://{GITHUB_USER}.github.io/{GITHUB_REPO}/')
    except urllib.error.HTTPError as e:
        log('GitHub 上傳失敗:', e.code, e.read().decode()[:200])

def main():
    now = datetime.now(); today = now.strftime('%Y-%m-%d')
    os.makedirs(DATA_DIR, exist_ok=True)
    body = find_vga_section(fetch_html())[1]
    if not body: log('找不到顯示卡分類'); sys.exit(1)
    items = parse_options(body)
    log(f'共解析到 {len(items)} 張純顯示卡(已排除支架)')
    if not items: sys.exit(1)

    prev, prev_date = {}, None
    cand = sorted((f, m.group(1)) for f in os.listdir(DATA_DIR)
                  if (m := re.match(r'vga_(\d{4}-\d{2}-\d{2})\.csv$', f)) and m.group(1) < today)
    if cand:
        prev_date = cand[-1][1]
        with open(os.path.join(DATA_DIR, cand[-1][0]), newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                try: prev[norm_name(row['產品名稱'])] = int(row['目前價格'])
                except Exception: pass

    with open(os.path.join(DATA_DIR, f'vga_{today}.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['產品ID', '產品名稱', '目前價格', '熱賣', '原始文字'])
        for it in items: w.writerow([it['id'], it['name'], it['price'], '是' if it['hot'] else '', it['raw']])

    hist = os.path.join(DATA_DIR, 'vga_history.csv')
    newf = not os.path.exists(hist)
    with open(hist, 'a', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        if newf: w.writerow(['日期', '時間', '產品ID', '產品名稱', '目前價格'])
        for it in items: w.writerow([today, now.strftime('%H:%M'), it['id'], it['name'], it['price']])

    report_html = build_report(items, prev, prev_date, today, now)
    report_path = os.path.join(BASE_DIR, 'vga_report.html')
    with open(report_path, 'w', encoding='utf-8') as f: f.write(report_html)
    log(f'報表已產生: {report_path}')

    upload_github(report_html, today)

    if prev:
        ch = [(it, prev[norm_name(it['name'])]) for it in items
              if norm_name(it['name']) in prev and prev[norm_name(it['name'])] != it['price']]
        log(f'與 {prev_date} 相比: 真實異動 {len(ch)} 項')

    if AUTO_OPEN_REPORT and '--quiet' not in sys.argv:
        try: os.startfile(report_path)
        except Exception: pass

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('[嚴重錯誤]', e); sys.exit(1)