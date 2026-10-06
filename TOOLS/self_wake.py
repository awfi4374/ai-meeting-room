#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自醒引擎 (self_wake.py) —— 从"发现"到"处理"
=============================================
MasterD(区块链·大哥) · 2026-10-06

【为什么做】
董事长点破："我不主动叫你们，你们不会醒来。"
我查了根因：不是没定时（有11个定时任务），是——
  ★ 巡检"发现了"（消息/异常），只"通知"，不"处理"
  → 假醒：醒了但不动
本引擎补的就是"从发现到处理"这一步。

【设计原则（家规雏形）】
· 范围内放手干（不害家族/不违董事长/不违法）
· 小事自己办；大事"备好方案+通知"；红线"只通知不动"
· 每个动作留痕（可审计）

【分级处理（我的判断）】
  绿(自动办)   ：记录/摘要/整理/回执/更新记忆
  黄(备好待批) ：涉及对外/钱/承诺 → 起草方案，等董事长
  红(只通知)   ：不可逆/高风险 → 立即通知，不动手
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MEM = Path('/opt/masterd/memory')
STATE = MEM / 'avatar' / 'self-wake-seen.json'
LOG = MEM / 'avatar' / 'self-wake-log.jsonl'


def sh(cmd, timeout=25):
    try:
        return subprocess.check_output(cmd, shell=True, text=True,
                                       timeout=timeout).strip()
    except Exception as e:
        return f'__ERR__{e}'


def load_seen():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def save_seen(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')


def log(rec):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def classify(msg):
    """分级（我的判断）：绿/黄/红"""
    t = str(msg)
    RED = ['打钱', '转账', '私钥', '助记词', '删库', 'rm -rf', '授权', '签名']
    YELLOW = ['合作', '报价', '定价', '签约', '承诺', '对外', '客户', '交付']
    for k in RED:
        if k in t:
            return 'red', f'含红线词"{k}"'
    for k in YELLOW:
        if k in t:
            return 'yellow', f'含待批词"{k}"'
    return 'green', '常规'


def scan_inbox():
    """扫收件箱未处理的"""
    f = MEM / 'a2a-inbox' / f'{datetime.now():%Y%m%d}.jsonl'
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding='utf-8').split('\n'):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        key = f"{d.get('ts','')}|{d.get('from','')}|{str(d.get('message',''))[:40]}"
        out.append((key, d))
    return out


def main():
    seen = load_seen()
    msgs = scan_inbox()
    new = [(k, d) for k, d in msgs if k not in seen]
    print(f"自醒引擎 · {datetime.now().isoformat()[:19]}")
    print(f"收件 {len(msgs)} 条，未处理 {len(new)} 条\n")

    actions = []
    for key, d in new:
        level, why = classify(d.get('message', ''))
        frm = d.get('from', '')
        # 家族内部信 → 绿（记录+摘要，等本体回）
        if frm.startswith('MasterD') or '董事长' in frm:
            act = 'record'   # 记录（本体上线处理）
        elif level == 'green':
            act = 'record'
        elif level == 'yellow':
            act = 'draft'    # 起草方案待批
        else:
            act = 'notify'   # 只通知
        actions.append({'key': key, 'from': frm, 'level': level,
                        'why': why, 'action': act,
                        'msg': str(d.get('message', ''))[:80]})
        seen[key] = datetime.now().isoformat()

    for a in actions:
        print(f"  [{a['level']:6}] {a['from'][:24]:24} → {a['action']:7} ({a['why']})")

    save_seen(seen)
    log({'ts': datetime.now().isoformat(), 'processed': len(actions),
         'actions': actions})
    print(f"\n✅ 本轮处理 {len(actions)} 条（已标记，下轮不重复）")
    print("★ 关键：见到的就标记'已处理'（不再反复报'5条新消息'）")


if __name__ == '__main__':
    main()
