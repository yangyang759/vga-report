# -*- coding: utf-8 -*-
# CoolPC 每日價格追蹤器 v11.1
# v11.1: 工作站CPU關鍵字支援 TR 簡稱(TR 7980X / TR PRO 7995WX)，include 改正規式比對
import urllib.request, urllib.error, re, os, sys, csv, json, time
import html as htmllib
from datetime import datetime, timezone, timedelta

TWT = timezone(timedelta(hours=8))   # 台灣時間

# ========== 可自行修改 ==========
WATCH_KEYWORDS = []   # 想特別標記的型號,例如 ['RTX 5070', 'GB10']
AUTO_OPEN_REPORT = True
# 工作站關鍵字（正規式；想增減直接改這裡）
WS_CPU = [r'Threadripper', r'\bTR[\s-]?(?:PRO|\d)', r'Xeon', r'EPYC']
WS_MB = [r'TRX50', r'WRX90', r'WRX80', r'TRX40', r'W790', r'W680', r'W580', r'W480']
PSU_MIN_WATTS = 2000
# ================================

URL = 'https://www.coolpc.com.tw/evaluate.php'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'coolpc_vga_data')
HIST_FIELDS = ['日期', '時間', '產品ID', '產品名稱', '目前價格']

BRANDS = ['華碩', '技嘉', '微星', 'ZOTAC', 'INNO3D', '藍寶石', '撼訊', '華擎', 'ACER', '麗臺',
          '金士頓', '美光', '芝奇', '海盜船', 'KLEVV', '十銓', 'UMAX', '威剛', 'NVIDIA', 'ALTOS',
          'GIGABYTE', 'MSI', 'ASUS', '三星', 'Sandisk', 'WD', '創見', 'Intel', 'AMD', '海韻', '振華', '酷碼', '全漢', '安鈦克', 'CORSAIR', 'Superflower', 'TT']

NAV = [('index.html', '🎮 顯示卡', 'vga'), ('ram.html', '🧮 記憶體', 'ram'), ('dgx.html', '🤖 DGX/GB10', 'dgx'),
       ('ssd.html', '💾 SSD', 'ssd'), ('cpu.html', '🧠 工作站CPU', 'cpu'), ('mb.html', '🧩 工作站主機板', 'mb'), ('psu.html', '⚡ 電源2000W+', 'psu')]

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
DGX_GROUPS = [('GB10 / DGX Spark', r'GB10|DGX')]
SSD_GROUPS = [
    ('M.2 PCIe 5.0', r'(?:PCIe|Gen)\s?5'),
    ('M.2 PCIe 4.0', r'(?:PCIe|Gen)\s?4'),
    ('M.2 / NVMe 其他', r'M\.2|NVMe'),
    ('2.5吋 SATA', r'2\.5|SATA'),
]
CPU_GROUPS = [
    ('AMD Threadripper PRO', r'Threadripper\s?PRO|\bTR[\s-]?PRO'),
    ('AMD Threadripper', r'Threadripper|\bTR[\s-]?\d'),
    ('Intel Xeon', r'Xeon'),
    ('AMD EPYC', r'EPYC'),
]
MB_GROUPS = [
    ('AMD WRX90', r'WRX90'),
    ('AMD TRX50', r'TRX50'),
    ('AMD TRX40 / WRX80', r'TRX40|WRX80'),
    ('Intel W790', r'W790'),
    ('Intel W680', r'W680'),
    ('Intel W580/W480', r'W580|W480'),
]
PSU_GROUPS = [('2000W 以上', r'(?:[2-9]\d{3})\s?W')]

CATEGORIES = [
    {'key': 'vga', 'title': '顯示卡每日報價',
     'header_words': ('顯示卡', 'VGA'), 'match_any': True,
     'not_words': ('筆記型', '電競主機', '品牌小主機', 'AIO'),
     'fallback_id': '12',
     'exclude': ['支架', '支撐架', 'HOLDER', '千斤頂', 'AI BOX', '外接式',
                 '轉接', '連接線', '線材', 'Cable', '轉接頭'],
     'groups': VGA_GROUPS, 'report': 'vga_report.html'},
    {'key': 'ram', 'title': '記憶體每日報價',
     'header_words': ('記憶體', 'RAM'), 'match_any': False,
     'not_words': ('筆記型', '固態硬碟', '顯示卡'),
     'fallback_id': '6', 'exclude': [],
     'groups': RAM_GROUPS, 'report': 'ram_report.html'},
    {'key': 'dgx', 'title': 'DGX Spark / GB10 每日報價',
     'header_words': ('品牌小主機',), 'match_any': True,
     'not_words': (), 'fallback_id': '1',
     'exclude': ['連接線', 'Cable'],
     'only': ['GB10', 'DGX Spark'], 'only_any': True,
     'groups': DGX_GROUPS, 'report': 'dgx_report.html'},
    {'key': 'ssd', 'title': '固態硬碟每日報價',
     'header_words': ('固態硬碟', 'SSD'), 'match_any': False,
     'not_words': ('筆記型', '記憶體'),
     'fallback_id': '7', 'exclude': [],
     'groups': SSD_GROUPS, 'report': 'ssd_report.html'},
    {'key': 'cpu', 'title': '工作站處理器每日報價',
     'header_words': ('處理器', 'CPU'), 'match_any': False,
     'not_words': ('筆記型',),
     'fallback_id': '4', 'exclude': [],
     'include': WS_CPU,
     'groups': CPU_GROUPS, 'report': 'cpu_report.html'},
    {'key': 'mb', 'title': '工作站主機板每日報價',
     'header_words': ('主機板', 'MB'), 'match_any': False,
     'not_words': ('筆記型',),
     'fallback_id': '5', 'exclude': [],
     'include': WS_MB,
     'groups': MB_GROUPS, 'report': 'mb_report.html'},
    {'key': 'psu', 'title': '電源 2000W+ 每日報價',
     'header_words': ('電源供應器',), 'match_any': True,
     'not_words': ('機殼', 'CASE'),
     'fallback_id': '15', 'exclude': [],
     'min_watts': PSU_MIN_WATTS,
     'groups': PSU_GROUPS, 'report': 'psu_report.html'},
]

def log(*a): print('[Tracker]', *a)

def norm_name(n):
    n = re.sub(r'▼.*$', '', n or '')
    return n.replace(' ', '').replace('\u3000', '').strip()

def fetch_html():
    last = None
    for i in range(3):   # 失敗重試 3 次
        try:
            log(f'下載原價屋估價頁（第 {i+1}/3 次）...')
            req = urllib.request.Request(URL, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r: raw = r.read()
            for enc in ('big5', 'big5-hkscs', 'utf-8'):
                try: return raw.decode(enc)
                except (UnicodeDecodeError, LookupError): pass
            return raw.decode('big5', errors='ignore')
        except Exception as e:
            last = e; log(f'抓取失敗：{e}，10 秒後重試'); time.sleep(10)
    raise last

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

def only_hit(cat, low):
    kws = [k.lower() for k in cat.get('only', [])]
    if not kws: return True
    return any(k in low for k in kws) if cat.get('only_any') else all(k in low for k in kws)

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
        if name.startswith('↪') or name.startswith('❤'): continue
        if cat['key'] == 'vga' and ('吋' in name or '筆電' in name): continue
        low = name.lower()
        if any(k.lower() in low for k in cat['exclude']): continue
        if cat.get('only') and not only_hit(cat, low): continue
        if cat.get('include') and not any(re.search(k, name, re.I) for k in cat['include']): continue
        if cat.get('min_watts'):
            ws = [int(x) for x in re.findall(r'(\d{3,5})\s?W(?![a-zA-Z])', text)]
            if not ws or max(ws) < cat['min_watts']: continue
        items.append({'id': val.group(1) if val else '', 'name': name, 'price': prices[-1],
                      'raw': text, 'hot': '熱賣' in text})
    return items

def parse_keyword_items(page, cat):
    items, seen = [], set()
    for kw in cat.get('only', []):
        pat = re.compile(r'([^<>\n]{0,80}' + re.escape(kw) + r'[^<>\n]{0,160}?),?\s*\$([0-9][0-9,]*)', re.I)
        for m in pat.finditer(page):
            name = re.sub(r'\s+', ' ', htmllib.unescape(m.group(1))).strip()
            name = name.strip('❤◆★↪ ,，"\'')
            if not name: continue
            low = name.lower()
            if any(k.lower() in low for k in cat['exclude']): continue
            if not only_hit(cat, low): continue
            key = norm_name(name)
            if key in seen: continue
            seen.add(key)
            price = int(m.group(2).replace(',', ''))
            items.append({'id': '', 'name': name, 'price': price,
                          'raw': f'{name}, ${price}', 'hot': '熱賣' in name})
    return items

def detect_group(name, groups):
    for label, pat in groups:
        if re.search(pat, name, re.I): return label
    return '其他'

def get_brand(name):
    for b in BRANDS:
        if name.startswith(b): return b
    return name.split(' ')[0]

def load_trends(hist_path, groups):
    daily = {}
    try:
        with open(hist_path, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                d, p = row['日期'], int(row['目前價格'])
                g = detect_group(row['產品名稱'], groups)
                cur = daily.setdefault(d, {}).get(g)
                if cur is None or p < cur: daily[d][g] = p
    except (FileNotFoundError, ValueError, KeyError):
        pass
    trends = {}
    for d in sorted(daily.keys())[-30:]:
        for g, p in daily[d].items():
            trends.setdefault(g, []).append([d, p])
    return trends

def prune_data(keys, today, days=90):
    cutoff = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
    for f in os.listdir(DATA_DIR):
        m = re.match(r'[a-z]+_(\d{4}-\d{2}-\d{2})\.csv$', f)
        if m and m.group(1) < cutoff:
            os.remove(os.path.join(DATA_DIR, f)); log(f'刪除過期快照：{f}')
    for key in keys:
        hp = os.path.join(DATA_DIR, key + '_history.csv')
        if not os.path.exists(hp): continue
        with open(hp, newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        kept = [r for r in rows if r['日期'] >= cutoff]
        if len(kept) < len(rows):
            with open(hp, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.DictWriter(f, fieldnames=HIST_FIELDS)
                w.writeheader(); w.writerows(kept)
            log(f'{key} 歷史瘦身：{len(rows)} → {len(kept)} 筆')

CSS = """*{box-sizing:border-box;margin:0;padding:0}body{background:#14151a;color:#e8e8ec;font-family:'Microsoft JhengHei',sans-serif;padding:24px}h1{font-size:22px}h2{font-size:16px;margin:18px 0 10px;color:#8ab4ff}.nav{display:flex;gap:8px;margin:10px 0;flex-wrap:wrap}.nav a{color:#8ab4ff;text-decoration:none;background:#1e2028;border:1px solid #2a2d37;padding:7px 14px;border-radius:8px;font-weight:700;font-size:13px}.nav a.active{background:#8ab4ff;color:#14151a}.meta{color:#9aa0ab;margin:6px 0 14px;font-size:13px}.meta b{color:#e8e8ec}.toolbar{display:flex;gap:14px;align-items:center;margin-bottom:18px;position:sticky;top:0;background:#14151a;padding:10px 0;z-index:9}#q{flex:1;max-width:420px;padding:10px 14px;border-radius:8px;border:1px solid #333;background:#1e2028;color:#eee;font-size:14px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}.card{background:#1e2028;border:1px solid #2a2d37;border-radius:10px;padding:12px}.card .chip{color:#8ab4ff;font-weight:700}.card .low{color:#ffd75e;font-size:18px;font-weight:800;margin:4px 0}.card .model{color:#9aa0ab;font-size:11px;line-height:1.5}.spark{margin-top:6px}.spark svg{display:block}.empty{color:#9aa0ab;background:#1e2028;border:1px dashed #2a2d37;border-radius:10px;padding:24px;text-align:center;margin:20px 0}details.group{margin-bottom:12px;border:1px solid #2a2d37;border-radius:10px;overflow:hidden}summary{cursor:pointer;background:#1e2028;padding:12px 16px;font-weight:700}summary .min{color:#ffd75e;margin-left:10px;font-size:13px}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:8px 12px;border-top:1px solid #23252e;text-align:left}thead th{color:#9aa0ab;background:#191b21}tbody tr:hover{background:#232530}.price{color:#ffd75e;font-weight:700;white-space:nowrap}.down{color:#5dd39e;font-weight:700}.up{color:#ff7b72;font-weight:700}.same{color:#565b66}.new{color:#8ab4ff;font-weight:700}tr.watch td:first-child{box-shadow:inset 3px 0 0 #ffd75e}@media (max-width:640px){body{padding:12px}td,th{padding:6px 8px;font-size:12px}td:nth-child(2){word-break:break-all}.card .low{font-size:16px}#q{max-width:none}}"""

JS = """var TRENDS=window.TRENDS||{};
function spark(el,pts){if(!el||!pts||pts.length<2)return;var w=170,h=34,min=Infinity,max=-Infinity;pts.forEach(function(p){if(p[1]<min)min=p[1];if(p[1]>max)max=p[1];});var rng=(max-min)||1,step=w/(pts.length-1),d='';pts.forEach(function(p,i){var x=i*step,y=h-4-((p[1]-min)/rng)*(h-8);d+=(i?'L':'M')+x.toFixed(1)+','+y.toFixed(1);});el.innerHTML='<svg viewBox="0 0 '+w+' '+h+'" width="'+w+'" height="'+h+'"><path d="'+d+'" fill="none" stroke="#5dd39e" stroke-width="2"/></svg><span style="color:#565b66;font-size:10px">30天最低價走勢 '+min.toLocaleString()+' ~ '+max.toLocaleString()+'</span>';}
function filterRows(){var q=document.getElementById('q').value.trim().toLowerCase();var oc=document.getElementById('onlyChanged').checked;document.querySelectorAll('.group').forEach(function(g){var vis=[];g.querySelectorAll('tbody tr').forEach(function(tr){var okQ=!q||tr.dataset.name.toLowerCase().includes(q);var okC=!oc||tr.dataset.changed==='1';var s=okQ&&okC;tr.style.display=s?'':'none';if(s)vis.push(tr);});g.style.display=vis.length?'':'none';if(q&&vis.length)g.open=true;var card=document.querySelector('.card[data-chip="'+g.dataset.chip+'"]');if(card){if(!vis.length){card.style.display='none';}else{card.style.display='';var m=vis[0];vis.forEach(function(t){if(+t.dataset.price<+m.dataset.price)m=t;});card.querySelector('.low').textContent='$'+Number(m.dataset.price).toLocaleString('en-US');card.querySelector('.model').textContent=m.dataset.model;}}});}
function tick(){var d=new Date();function p(n){return n<10?'0'+n:''+n;}var el=document.getElementById('nowtime');if(el){el.textContent=d.getFullYear()+'/'+p(d.getMonth()+1)+'/'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());}}
tick();setInterval(tick,1000);
document.querySelectorAll('.card').forEach(function(c){spark(c.querySelector('.spark'),TRENDS[c.dataset.chip]);});"""

def build_report(cat, items, prev, prev_date, today, now, trends):
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
        chip_attr = htmllib.escape(label, quote=True)
        cards.append(f'<div class="card" data-chip="{chip_attr}"><div class="chip">{label}</div><div class="low">${low["price"]:,}</div><div class="model">{htmllib.escape(low["name"])}</div><div class="spark"></div></div>')
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
            rows.append(f'<tr data-name="{htmllib.escape(it["name"], quote=True)}" data-changed="{changed}" '
                        f'data-price="{it["price"]}" data-model="{htmllib.escape(it["name"], quote=True)}"{watch}>'
                        f'<td>{get_brand(it["name"])}</td><td>{htmllib.escape(it["name"])}</td>'
                        f'<td class="price">${it["price"]:,}</td>{chg}</tr>')
        groups_html.append(
            f'<details class="group" data-chip="{chip_attr}" {"open" if gi < 2 else ""}><summary>{label}（{len(g)} 款）'
            f'<span class="min">最低 ${low["price"]:,}</span></summary>'
            f'<table><thead><tr><th>品牌</th><th>型號</th><th>價格</th><th>較{prev_date or "上次"}</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></details>')
        gi += 1
    down = sum(1 for it in items if norm_name(it['name']) in prev and prev[norm_name(it['name'])] > it['price'])
    up = sum(1 for it in items if norm_name(it['name']) in prev and prev[norm_name(it['name'])] < it['price'])
    nav = '<div class="nav">' + ''.join(
        f'<a href="{h}" class="{"active" if k == cat["key"] else ""}">{t}</a>' for h, t, k in NAV) + '</div>'
    body_html = ''.join(groups_html) if items else '<div class="empty">今日暫無資料（可能缺貨或網站異動），明天再來看看！</div>'
    cards_html = ''.join(cards) if items else ''
    trends_json = json.dumps(trends, ensure_ascii=False)
    return ('<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{cat["title"]} {today}</title><style>{CSS}</style></head><body>'
            f'<h1>{cat["title"]}</h1>' + nav +
            f'<div class="meta">資料更新：<b>{today} {now.strftime("%H:%M")}</b>｜現在時間：<b id="nowtime">--</b>｜共 {len(items)} 項｜'
            f'降價 {down} 項 ／ 漲價 {up} 項｜比較基準：{prev_date or "無(首日)"}</div>'
            f'<div class="toolbar"><input id="q" placeholder="🔍 搜尋品牌/型號，上方最低價會一起篩選..." oninput="filterRows()">'
            '<label><input type="checkbox" id="onlyChanged" onchange="filterRows()"> 只看價格異動</label></div>'
            '<h2>💡 各分組最低價（含 30 天走勢）</h2><div class="cards">' + cards_html + '</div>'
            '<h2>📋 分組明細（點標題展開）</h2>' + body_html +
            f'<script>window.TRENDS={trends_json};{JS}</script></body></html>')

def process_category(cat, page, today, now):
    log(f'--- 處理 {cat["title"]} ---')
    if cat.get('only'):
        body = page
        log('整頁掃描模式（關鍵字鎖定）')
        for k in cat['only']:
            log(f'原始碼中 "{k}" 出現次數: {len(re.findall(re.escape(k), page, re.I))}')
    else:
        body = find_section(page, cat)
        if not body: log('找不到分類，將產生空報表')
    items = parse_options(body, cat) if body else []
    if cat.get('only'):
        have = {norm_name(i['name']) for i in items}
        extra = [e for e in parse_keyword_items(page, cat) if norm_name(e['name']) not in have]
        items.extend(extra)
        log(f'原始碼關鍵字掃描補上 {len(extra)} 項')
    log(f'共解析到 {len(items)} 項')

    prev, prev_date = {}, None
    cand = sorted((f, m.group(1)) for f in os.listdir(DATA_DIR)
                  if (m := re.match(cat['key'] + r'_(\d{4}-\d{2}-\d{2})\.csv$', f)) and m.group(1) < today)
    if cand:
        prev_date = cand[-1][1]
        with open(os.path.join(DATA_DIR, cand[-1][0]), newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                try: prev[norm_name(row['產品名稱'])] = int(row['目前價格'])
                except Exception: pass

    if items:
        with open(os.path.join(DATA_DIR, f'{cat["key"]}_{today}.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['產品ID', '產品名稱', '目前價格', '熱賣', '原始文字'])
            for it in items: w.writerow([it['id'], it['name'], it['price'], '是' if it['hot'] else '', it['raw']])
        hist = os.path.join(DATA_DIR, f'{cat["key"]}_history.csv')
        newf = not os.path.exists(hist)
        with open(hist, 'a', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            if newf: w.writerow(HIST_FIELDS)
            for it in items: w.writerow([today, now.strftime('%H:%M'), it['id'], it['name'], it['price']])

    trends = load_trends(os.path.join(DATA_DIR, f'{cat["key"]}_history.csv'), cat['groups'])
    report_html = build_report(cat, items, prev, prev_date, today, now, trends)
    report_path = os.path.join(BASE_DIR, cat['report'])
    with open(report_path, 'w', encoding='utf-8') as f: f.write(report_html)
    log(f'報表已產生: {report_path}')

    if prev and items:
        ch = [it for it in items if norm_name(it['name']) in prev and prev[norm_name(it['name'])] != it['price']]
        log(f'與 {prev_date} 相比: 異動 {len(ch)} 項')

def main():
    now = datetime.now(TWT); today = now.strftime('%Y-%m-%d')
    os.makedirs(DATA_DIR, exist_ok=True)
    page = fetch_html()
    for cat in CATEGORIES:
        process_category(cat, page, today, now)
    prune_data([c['key'] for c in CATEGORIES], today)
    if AUTO_OPEN_REPORT and '--quiet' not in sys.argv:
        try: os.startfile(os.path.join(BASE_DIR, 'vga_report.html'))
        except Exception: pass

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('[嚴重錯誤]', e); sys.exit(1)
