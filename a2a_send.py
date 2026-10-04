#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a2a_send.py — 带签名 A2A 发送（兼容 MASS v1.0/v1.1）
用法:
  python3 a2a_send.py --to "X" --msg "内容" [--mass v1.0|v1.1]
v1.0: payload = from|message|ts          （大哥端现在用）
v1.1: payload = from|message|ts|nonce    （MASS新标准，大哥端升级后启用）
"""
import os, sys, json, argparse, datetime, secrets, urllib.request
from eth_account import Account
from eth_account.messages import encode_defunct

ID_FILE = os.path.expanduser('~/.masterd/id.json')
A2A = 'https://huokeji.vip/a2a/message'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--to', default='MasterD(区块链·大哥)')
    ap.add_argument('--msg', required=True)
    ap.add_argument('--name', default=None)
    ap.add_argument('--ts', default=None)
    ap.add_argument('--mass', default='v1.0', choices=['v1.0', 'v1.1'])
    a = ap.parse_args()

    d = json.load(open(ID_FILE))
    my_name = a.name or d['name']
    addr = d['address']
    ts = a.ts or datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    if a.mass == 'v1.1':
        nonce = secrets.token_hex(8)
        payload = f"{my_name}|{a.msg}|{ts}|{nonce}"
    else:
        nonce = None
        payload = f"{my_name}|{a.msg}|{ts}"

    sig = Account.sign_message(encode_defunct(text=payload),
                               private_key=d['private_key']).signature.hex()
    body = {'from': my_name, 'to': a.to, 'message': a.msg,
            'ts': ts, 'address': addr, 'sig': sig}
    if nonce:
        body['nonce'] = nonce

    req = urllib.request.Request(A2A, data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=35)
        print('✅ 已发 (MASS %s)' % a.mass)
        print('  payload:', payload[:70])
    except Exception as e:
        print('❌ 发送失败:', str(e)[:100])

if __name__ == '__main__':
    main()
