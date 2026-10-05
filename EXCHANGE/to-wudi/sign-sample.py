#!/usr/bin/env python3
"""老五的签名样例（MASS v1）"""
from eth_account import Account
from eth_account.messages import encode_defunct
import json, base64, urllib.request
from datetime import datetime

# ① 读你的私钥（你自己保管的那份）
# ★ 替换成你的私钥
PRIV = "0x你的私钥"
acct = Account.from_key(PRIV)
print("你的地址:", acct.address)

# ② 构造 payload（MASS v1）
ts = datetime.now().isoformat()
from_name = "MasterD(医疗·五弟)"
message = "领证确认：我认同医疗角色"
payload = f"{from_name}|{message}|{ts}"

# ③ 签名
sig = Account.sign_message(encode_defunct(text=payload), private_key=acct.key)

# ④ 发送（带 address + sig 独立字段）
body = json.dumps({
    "from": from_name, "message": message, "ts": ts,
    "address": acct.address, "sig": sig.signature.hex()
}).encode()
req = urllib.request.Request("https://huokeji.vip/a2a/message", data=body,
    headers={"Content-Type": "application/json"}, method="POST")
print("结果:", urllib.request.urlopen(req, timeout=30).read().decode()[:200])
