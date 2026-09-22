import sys,json,re,time,html
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import openpyxl,urllib.request,urllib.error
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prolitech/scripts'))
from export_open_prices_csv import load_env,query_mysql
OUT=Path(__file__).parent
source=r'C:\Work\ПОСТАЧАЛЬНИКИ\Магнум Стіл\18-09-2026\19.xlsx'
w=openpyxl.load_workbook(source)
rows=[list(r[:2]) for r in w.active.values]
skus=list(dict.fromkeys(str(r[1]).strip() for r in rows))
ids=','.join("CONVERT(0x"+s.encode().hex()+" USING utf8)" for s in skus)
db=query_mysql(load_env(ROOT/'prolitech/.env_open'),f'SELECT p.sku,p.product_id,pd.name FROM {{prefix}}product p LEFT JOIN {{prefix}}product_description pd ON pd.product_id=p.product_id AND pd.language_id=1 WHERE TRIM(p.sku) IN ({ids})')
lookup={}
for sku,pid,name in db: lookup.setdefault(sku.strip(),[]).append([pid,html.unescape(name or '')])
print('DB matched',len(lookup),'of',len(skus),flush=True)
(OUT/'names.json').write_text(json.dumps(lookup,ensure_ascii=False),encoding='utf-8')
def check(url):
    result={'url':url}
    for attempt in range(2):
        try:
            try: response=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30)
            except urllib.error.HTTPError as e: response=e
            content=response.read().decode('utf-8','replace')
            r=SimpleNamespace(status_code=response.code,url=response.url,text=content)
            def tag(t): return ' | '.join(html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall('<'+t+r'\b[^>]*>(.*?)</'+t+'>',content,re.S|re.I))
            title=tag('title')
            h1=tag('h1')
            status='Перевірити вручну'
            reason='Немає достатніх ознак сторінки товару'
            if r.status_code in (404,410): status='URL не існує';reason=f'HTTP {r.status_code}'
            elif r.status_code==200:
                if re.search(r'сторінк[ау].{0,25}не знайден|страниц[ауы].{0,25}не найден|товар.{0,20}(видален|удален)|page not found',h1+' '+title,re.I): status='URL не існує';reason='Повідомлення про відсутню сторінку'
                elif 'schema.org/Product' in content or re.search(r'"@type"\s*:\s*"Product"',content) or 'data-qaid="product_name"' in content: status='Сторінка існує';reason='Знайдено сторінку товару'
            else: reason=f'HTTP {r.status_code}; не підтверджує видалення'
            result.update(http=r.status_code,final_url=r.url,title=title,h1=h1,status=status,reason=reason,checked=datetime.now(timezone.utc).isoformat(),attempts=attempt+1)
            if status=='URL не існує' or r.status_code>=500 or r.status_code==429:
                if attempt==0: time.sleep(1);continue
            if status!='Сторінка існує': (OUT/('page_'+re.sub(r'\W','_',url)[-120:]+'.html')).write_text(r.text,encoding='utf-8')
            return result
        except (OSError,urllib.error.URLError) as e:
            result.update(http=None,final_url='',title='',h1='',status='Помилка доступу',reason=type(e).__name__,checked=datetime.now(timezone.utc).isoformat(),attempts=attempt+1)
    return result
urls=list(dict.fromkeys(r[0] for r in rows))
results={}
with ThreadPoolExecutor(max_workers=6) as pool:
    futures={pool.submit(check,u):u for u in urls}
    for f in as_completed(futures):
        results[futures[f]]=f.result()
        if len(results)%30==0: print('Checked',len(results),'/',len(urls),flush=True)
        (OUT/'checks.json').write_text(json.dumps(results,ensure_ascii=False),encoding='utf-8')
data={'source':source,'sheet':w.active.title,'rows':rows,'names':lookup,'checks':results}
(OUT/'data.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
from collections import Counter
print(dict(Counter(x['status'] for x in results.values())),flush=True)
