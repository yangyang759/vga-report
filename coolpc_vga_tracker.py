# -*- coding: utf-8 -*-
# CoolPC 每日價格追蹤器 v9.0
# v9.0: 過濾↪贈品備註行 + 頁面顯示現在時間/更新時間 + 新增 DGX Spark 分頁
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
          '金士頓', '美光', '芝奇', '海盜船', 'KLEVV', '十銓', 'UMAX', '威剛', 'NVIDIA', 'ALTOS']

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
    ('DDR5 桌上型', r
