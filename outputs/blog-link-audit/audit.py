import requests, json, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
BASE='https://prolitech.com.ua/'
OUT=Path('outputs/blog-link-audit')
def get(u):
 for i in range(3):
  try:
   r=requests.get(u,timeout=45);r.raise_for_status();return BeautifulSoup(r.content,'html.parser')
  except Exception:
   if i==2:raise
root=get(BASE+'blog/')
# Include all blog sections from the navigation and pagination.
seeds={BASE+'blog/'}
for a in root.select('nav a'):
 if a.get_text(' ',strip=True) in ['Блог','Статті','Самогоноваріння та дистиляція','Домашнє пивоваріння','Виноробство','Рецепти']:
  seeds.add(urljoin(BASE,a.get('href','')))
queue=list(seeds); seen=set(); articles={}
while queue:
 u=queue.pop(0)
 if u in seen:continue
 seen.add(u); s=root if u==BASE+'blog/' else get(u)
 for a in s.select('.us-news-block-title'):
  articles[urljoin(u,a['href'])]=a.get_text(' ',strip=True)
 for a in s.select('.pagination a'):
  v=urljoin(u,a['href'])
  if v not in seen:queue.append(v)
 print('LIST',u,'articles',len(articles),flush=True)
(OUT/'inventory.json').write_text(json.dumps({'listing_pages':list(seen),'articles':articles},ensure_ascii=False,indent=2),encoding='utf-8')
def inspect(item):
 u,t=item
 try:
  s=get(u); body=s.select_one('.us-blog-post-text')
  if body is None:return {'url':u,'title':t,'error':'No article body'}
  links=[{'text':a.get_text(' ',strip=True),'url':urljoin(u,a['href'])} for a in body.select('a[href]') if a['href'].strip() and not a['href'].startswith('#')]
  result={'url':u,'title':s.h1.get_text(' ',strip=True),'links':links,'body_chars':len(body.get_text()),'recommended_count':len(s.select('.us-product-layout')),'text':body.get_text(' ',strip=True)}
  print('ARTICLE',len(links),result['title'],flush=True)
  return result
 except Exception as e:return {'url':u,'title':t,'error':str(e)}
with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(inspect,articles.items()))
(OUT/'audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('TOTAL',len(results),'ZERO',sum(not r.get('links') for r in results),'ERRORS',sum('error' in r for r in results),flush=True)
