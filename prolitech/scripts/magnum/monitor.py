#!/usr/bin/env python3
"""Weekly Magnum URL monitor. Python 3.6+, standard library only."""
import argparse
import csv
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

BASE = Path(__file__).resolve().parent
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ALLOWED_HOSTS = {'hmel-master.com', 'www.hmel-master.com'}


def validate_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ('http', 'https') or p.hostname not in ALLOWED_HOSTS or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError('URL outside allowed supplier domain')
    return url


class SupplierRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_products(path):
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        book = ET.fromstring(z.read('xl/workbook.xml'))
        first = book.find('s:sheets/s:sheet', NS)
        rid = first.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next(r.attrib['Target'] for r in rels if r.attrib['Id'] == rid)
        sheet_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        sheet = ET.fromstring(z.read(sheet_path))
        result = []
        columns = {'url': 'A', 'sku': 'B', 'name': 'C'}
        for row in sheet.findall('s:sheetData/s:row', NS):
            cells = {}
            for c in row.findall('s:c', NS):
                col = ''.join(x for x in c.attrib['r'] if x.isalpha())
                v = c.find('s:v', NS)
                value = v.text if v is not None and v.text else ''
                if c.attrib.get('t') == 's':
                    value = strings[int(value)]
                elif c.attrib.get('t') == 'inlineStr':
                    value = ''.join(c.find('s:is', NS).itertext())
                cells[col] = value.strip()
            if not any(cells.values()):
                continue
            lowered = {k: v.lower() for k, v in cells.items()}
            if 'url' in lowered.values():
                columns['url'] = next(k for k, v in lowered.items() if v == 'url')
                for key, labels in [('sku', ('sku', 'артикул')), ('name', ('назва', 'назва товару', 'назва товару в пролітех'))]:
                    found = [k for k, v in lowered.items() if v in labels]
                    if found:
                        columns[key] = found[0]
                continue
            url = cells.get(columns['url'], '')
            if not url:
                raise ValueError('Missing URL at Excel row ' + row.attrib['r'])
            validate_url(url)
            result.append({'url': url, 'sku': cells.get(columns['sku'], ''), 'name': cells.get(columns['name'], '')})
    if not result:
        raise ValueError('Workbook has no products')
    return result


def request_status(url):
    try:
        opener = urllib.request.build_opener(SupplierRedirect())
        req = urllib.request.Request(validate_url(url), headers={'User-Agent': 'Mozilla/5.0 (Magnum URL monitor)'})
        with opener.open(req, timeout=25) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError, ValueError):
        return None


def check_url(url):
    first = request_status(url)
    if first == 404 or first is None or first in (429, 500, 502, 503, 504):
        time.sleep(2)
        second = request_status(url)
        if first == second == 404:
            return {'status': 'missing', 'http': 404, 'attempts': [first, second]}
        # A single 404 is inconclusive, even if it occurred on the retry.
        if second is not None and 200 <= second < 300:
            return {'status': 'exists', 'http': second, 'attempts': [first, second]}
        return {'status': 'unknown', 'http': second, 'attempts': [first, second]}
    return {'status': 'exists' if first is not None and 200 <= first < 300 else 'unknown', 'http': first, 'attempts': [first]}


def atomic_json(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(tmp), str(path))


def telegram(config, text):
    recipients = list(dict.fromkeys(config.get('chat_ids') or [config['chat_id']]))
    failed = []
    for recipient in recipients:
        try:
            telegram_one(config, recipient, text)
        except RuntimeError:
            failed.append(recipient)
    if failed:
        raise RuntimeError('Telegram delivery failed for {} recipient(s); pending alerts retained'.format(len(failed)))


def telegram_one(config, recipient, text):
    payload = json.dumps({'chat_id': recipient, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}).encode('utf-8')
    url = 'https://api.telegram.org/bot' + config['bot_token'] + '/sendMessage'
    try:
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
        if not result.get('ok'):
            raise RuntimeError('Telegram rejected message')
    except Exception:
        # Never include exception URLs containing the bot token in logs.
        raise RuntimeError('Telegram delivery failed; pending alerts retained') from None


def update_state(previous, results):
    state = dict(previous)
    for url, result in results.items():
        item = dict(state.get(url, {'missing': False, 'notified': False}))
        if result['status'] == 'exists':
            item = {'missing': False, 'notified': False}
        elif result['status'] == 'missing':
            item['missing'] = True
        state[url] = item
    return state


def alert_groups(products, results, state):
    grouped = {}
    for p in products:
        url = p['url']
        if results[url]['status'] == 'missing' and not state[url]['notified']:
            grouped.setdefault(url, []).append(p)
    for url, entries in grouped.items():
        labels = html.escape('\n'.join(p['sku'] + ' — ' + (p['name'] or 'Назва не вказана') for p in entries)[:1800])
        # Keep supplier-sourced text safely within Telegram message limits.
        text = '<b>Магнум: сторінка зникла (404)</b>\n\n' + labels + '\n\n' + html.escape(url) + '\n\n404 підтверджено двома запитами.'
        yield url, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Check URLs without sending or updating baseline')
    parser.add_argument('--inspect', action='store_true', help='Validate Excel without network requests')
    args = parser.parse_args()
    products = read_products(BASE / '19.xlsx')
    urls = list(dict.fromkeys(p['url'] for p in products))
    if args.inspect:
        print(json.dumps({'rows': len(products), 'urls': len(urls)}, ensure_ascii=False))
        return
    config = {}
    if not args.dry_run:
        config = json.loads((BASE / 'config.json').read_text(encoding='utf-8-sig'))
        if not config.get('bot_token') or not config.get('chat_id'):
            raise ValueError('Configure bot_token and chat_id in config.json')
    # Linux hosting: OS releases the lock even after process termination.
    import fcntl
    with (BASE / 'monitor.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another run is active')
            return
        state_path = BASE / 'state.json'
        previous = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = dict(zip(urls, pool.map(check_url, urls)))
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        state = update_state(previous, results)
        alerts = list(alert_groups(products, results, state))
        report = {'checked_utc': stamp, 'rows': len(products), 'urls': len(urls), 'new_missing': len(alerts), 'results': results}
        atomic_json(BASE / ('dry-run.json' if args.dry_run else 'latest-results.json'), report)
        with (BASE / ('dry-run.csv' if args.dry_run else 'latest-results.csv')).open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['URL', 'SKU', 'Назва', 'HTTP', 'Стан', 'Перевірено UTC'])
            for p in products:
                r = results[p['url']]
                writer.writerow([p['url'], p['sku'], p['name'], r['http'], r['status'], stamp])
        if not args.dry_run:
            atomic_json(state_path, state)
            for url, message in alerts:
                telegram(config, message)
                state[url]['notified'] = True
                atomic_json(state_path, state)
                time.sleep(1.1)
        counts = {key: sum(r['status'] == key for r in results.values()) for key in ('exists', 'missing', 'unknown')}
        print(json.dumps({'checked_utc': stamp, 'dry_run': args.dry_run, 'counts': counts, 'alerts': len(alerts)}))
        if counts['unknown']:
            print('Some URLs could not be verified; see latest results. They are not classified as missing.', file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(1)
