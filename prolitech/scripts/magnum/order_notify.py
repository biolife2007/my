#!/usr/bin/env python3
"""New OpenCart orders from both sites -> the existing private Telegram chat."""
import argparse
import fcntl
import html
import json
import subprocess
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from monitor import atomic_json, telegram

BASE = Path(__file__).resolve().parent
SITES = {'prolitech': 'Пролітех (prolitech.com.ua)', 'prolimax': 'ПроліМакс (prolimax.com.ua)'}
PHP = '/opt/alt/php74/usr/bin/php'


def read_orders(site, since=None):
    args = [PHP, str(BASE / 'orders_reader.php'), site]
    if since is not None:
        args.append(str(since))
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, universal_newlines=True)
    if result.returncode:
        raise RuntimeError('Cannot read orders: ' + site)
    data = json.loads(result.stdout)
    if since is not None and int(data['max_history_id']) < since:
        raise RuntimeError('History counter moved backwards: ' + site)
    return data


def message(site, order, test=False):
    amount = (Decimal(str(order['total'])) * Decimal(str(order['currency_value']))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    currency = order['currency_code']
    amount_text = format(amount, ',.2f').replace(',', ' ').replace('.', ',')
    date = datetime.strptime(order['date_added'], '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M:%S')
    return ('<b>' + ('ТЕСТ — приклад повідомлення' if test else 'Нове замовлення') + '</b>\n'
            'Сайт: ' + html.escape(SITES[site]) + '\n'
            'Номер: ' + html.escape(str(order['order_id'])) + '\n'
            'Дата: ' + date + '\n'
            'Сума: ' + amount_text + ' ' + html.escape(currency) + '\n'
            'Оплата: ' + ('Сплачене' if int(order['is_paid']) == 1 else 'Не сплачене'))


def process_site(site, state, config, save):
    item = state[site]
    data = read_orders(site, item['history_id'])
    delivered = set(item.get('delivered', []))
    for order in data['orders']:
        hid = int(order['order_history_id'])
        if hid in delivered:
            continue
        telegram(config, message(site, order))
        delivered.add(hid)
        item['delivered'] = sorted(delivered)
        save()
        time.sleep(1.1)
    item['history_id'] = int(data['max_history_id'])
    item['delivered'] = []
    save()
    return len(data['orders'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true')
    parser.add_argument('--test', action='store_true')
    args = parser.parse_args()
    with (BASE / 'orders.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        path = BASE / 'orders-state.json'
        if args.init:
            if path.exists():
                print('Already initialized; existing state preserved')
                return
            state = {site: {'history_id': int(read_orders(site)['max_history_id']), 'delivered': []} for site in SITES}
            atomic_json(path, state)
            print('Both sites initialized; old orders excluded')
            return
        config = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
        if args.test:
            demo = {'order_id':'ТЕСТ', 'date_added':datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'total':'0', 'currency_value':'1', 'currency_code':'UAH', 'is_paid':0}
            for site in SITES:
                telegram(config, message(site, demo, True))
                time.sleep(1.1)
            print('Two labeled test notifications delivered; no orders created')
            return
        state = json.loads(path.read_text(encoding='utf-8'))
        def save(): atomic_json(path, state)
        errors = []
        for site in SITES:
            try:
                count = process_site(site, state, config, save)
                print(site + ': ' + str(count) + ' new order(s)', flush=True)
            except Exception:
                errors.append(site)
                print('ERROR: order delivery pending for ' + site, flush=True)
        if errors:
            raise RuntimeError('Some sites failed; retry on next cron run')


if __name__ == '__main__':
    main()
