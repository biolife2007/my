import urllib.request,re,html,concurrent.futures,json
from pathlib import Path
ids=[3151111842,3151111843,3151111844,3151111845,3151111846,3151111847]
def clean(t):return ' '.join(html.unescape(re.sub('<[^>]*>',' ',t)).split())
def get(i):
 u=f'https://hmel-master.com/ua/p{i}-mednaya-kryshka-pod.html'
 t=urllib.request.urlopen(u,timeout=30).read().decode('utf-8')
 products=[json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>',t,re.S)]
 product=next(x for x in products if x.get('@type')=='Product')
 attrs={}
 for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>',t,re.S):
  cells=[clean(x) for x in re.findall(r'<td\b[^>]*>(.*?)</td>',tr,re.S)]
  if len(cells)==2:attrs[cells[0]]=cells[1]
 assert product['offers']['priceCurrency']=='UAH'
 assert attrs.get('Розмір'),attrs
 return [u,product['sku'],float(product['offers']['price']),attrs['Розмір']]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 rows=list(pool.map(get,ids))
 Path('outputs/url_audit_20260922/copper_prices.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
 print(json.dumps(rows,ensure_ascii=True))
