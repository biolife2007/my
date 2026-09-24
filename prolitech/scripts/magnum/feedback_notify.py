import argparse
import fcntl
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from monitor import atomic_json, telegram

BASE=Path(__file__).resolve().parent
SITES={'prolitech':'Пролітех','prolimax':'ПроліМакс'}
TYPES={'blog':'Коментар блогу','article':'Коментар блогу','review':'Відгук про товар','question':'Питання','answer':'Відповідь на питання'}

def read(site):
    p=subprocess.run(['/opt/alt/php74/usr/bin/php',str(BASE/'feedback_reader.php'),site],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=45)
    if p.returncode:raise RuntimeError('Feedback read failed: '+site)
    return json.loads(p.stdout)

def key(row):return row['kind']+':'+str(row['id'])

def baseline(rows):
    return {key(r):{'seen':True,'answer_hash':r['answer_hash']} for r in rows}

def message(site,kind,date):
    try: stamp=datetime.strptime(date,'%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y, %H:%M')
    except ValueError:stamp=datetime.now().strftime('%d.%m.%Y, %H:%M')
    return stamp+' | '+TYPES[kind]+' | '+SITES[site]

def process(site,rows,state,config,save):
    count=0
    for row in sorted(rows,key=lambda r:(r['date_added'],r['kind'],int(r['id']))):
        item=state.setdefault(key(row),{'seen':False,'answer_hash':''})
        if not item['seen']:
            telegram(config,message(site,row['kind'],row['date_added']))
            item['seen']=True
            save();count+=1;time.sleep(1.1)
        if row['kind']=='question' and row['answer_hash']!=item['answer_hash']:
            if row['answer_hash']:
                telegram(config,message(site,'answer',row['date_modified']))
                count+=1;time.sleep(1.1)
            item['answer_hash']=row['answer_hash']
            save()
    return count

def main():
    p=argparse.ArgumentParser();p.add_argument('--init',action='store_true');p.add_argument('--test',action='store_true');args=p.parse_args()
    with (BASE/'feedback.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        path=BASE/'feedback-state.json'
        if args.init:
            if path.exists():print('Existing baseline preserved');return
            state={s:baseline(read(s)) for s in SITES};atomic_json(path,state)
            print('Initialized both sites; historical records excluded');return
        config=json.loads((BASE/'config.json').read_text(encoding='utf-8'))
        if args.test:
            stamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for s in SITES:
                telegram(config,'ТЕСТ\n'+message(s,'review',stamp));time.sleep(1.1)
            print('Test notifications delivered to configured recipients');return
        state=json.loads(path.read_text(encoding='utf-8'))
        errors=[]
        for s in SITES:
            try:print(s+': '+str(process(s,read(s),state[s],config,lambda:atomic_json(path,state)))+' notification(s)',flush=True)
            except Exception:errors.append(s);print('ERROR: feedback delivery pending for '+s,flush=True)
        if errors:raise RuntimeError('Pending feedback will retry next run')

if __name__=='__main__':main()
