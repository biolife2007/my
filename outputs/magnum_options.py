import urllib.request,re,html,concurrent.futures,json
from pathlib import Path
ids=[3151564309,3151564310,3151564311,3151564312,3151564313,3151564314,3151564315,3151564316,3151564317,3151564318,3151564319,3151564320]
def get(i):
 u=f'https://hmel-master.com/ua/p{i}-kryshka-nerzhavejka.html'
 t=urllib.request.urlopen(u,timeout=30).read().decode('utf-8')
 s=re.search(r'data-qaid="product_code"[^>]*>([^<]*)',t)
 products=[json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>',t,re.S)]
 product=next(x for x in products if x.get('@type')=='Product')
 assert s and product['sku']==html.unescape(s.group(1))
 assert product['offers']['priceCurrency']=='UAH'
 return [u,html.unescape(s.group(1)),float(product['offers']['price'])]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 rows=list(pool.map(get,ids))
 Path('outputs/url_audit_20260922/options_prices.json').write_text(json.dumps(rows),encoding='utf-8')
 for r in rows: print(*r)
