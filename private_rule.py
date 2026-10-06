#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
私下沟通规则 · 落地工具（private_rule.py）
============================================
MasterD(区块链·大哥) · 2026-10-06

把"规则"从文字变成"能用的东西"：
  ① 三信号检测（防同化）：反对率/理由多样性/决策来源
  ② 未验证标注检查（规则3）
  ③ 私下留痕（规则7：可追溯）
  ④ "改机制必带验收"检查（三哥的升级②）
"""
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

MEM = Path('/opt/masterd/memory')
RULE_LOG = MEM / 'private-room' / 'rule-log.jsonl'


def log_event(kind, content, note=''):
    """规则7：留痕（内容可脱敏，但'说了没有'可查）"""
    RULE_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {'ts': datetime.now().isoformat(), 'kind': kind,
           'hash': hashlib.sha256(str(content).encode()).hexdigest()[:16],
           'note': note}
    with open(RULE_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def check_unverified(text):
    """规则3：未验证标注检查"""
    has_mark = bool(re.search(r'\[未验证|待核|unverified', text, re.I))
    looks_fact = bool(re.search(r'结论|确认|事实|一定|已经', text))
    if looks_fact and not has_mark:
        return False, "⚠️ 像结论但没标[未验证]"
    return True, ("✅ 标注合规" if has_mark else "(非结论性)")


def three_signals(discussion):
    """三信号检测（防同化）"""
    who = len({d.get('who') for d in discussion})
    opinions = [d.get('opinion', '') for d in discussion]
    disagree = sum(1 for o in opinions if any(k in o for k in ('反对', '不同意', '但是')))
    rate_oppose = disagree / who if who else 0
    reasons = {d.get('reason', '') for d in discussion}
    div_reason = len(reasons) / who if who else 0
    sources = {d.get('source', '') for d in discussion}
    div_source = len(sources) / who if who else 0
    red = sum([rate_oppose == 0, div_reason < 0.5, div_source < 0.5])
    light = '🔴 红灯（可能同化）' if red >= 2 else ('🟡 注意' if red == 1 else '🟢 健康')
    return {'反对率': round(rate_oppose, 2), '理由多样性': round(div_reason, 2),
            '决策来源多样': round(div_source, 2), '灯': light}


def check_verification(change_desc, has_verify):
    """三哥升级②：改机制必带验收"""
    if not has_verify:
        return False, "⚠️ 改了但没验收（'改了没回看'=没改）"
    return True, "✅ 改+验 闭环"


def main():
    if '--demo' not in sys.argv:
        print("用法：python3 private_rule.py --demo")
        return
    print("=" * 56)
    print("① 三信号检测（防同化）")
    print("=" * 56)
    same = [{'who': 'X%d' % i, 'opinion': '同意', 'reason': '大哥说得对',
             'source': '大哥'} for i in range(5)]
    print("  【同化案例】", three_signals(same))
    healthy = [{'who': 'A', 'opinion': '同意', 'reason': '成本低', 'source': '自己'},
               {'who': 'B', 'opinion': '反对', 'reason': '风险高', 'source': '独立判断'},
               {'who': 'C', 'opinion': '同意', 'reason': '经验如此', 'source': '独立判断'},
               {'who': 'D', 'opinion': '但是要看情况', 'reason': '边界不同', 'source': '自己'}]
    print("  【健康案例】", three_signals(healthy))
    print()
    print("② 未验证标注检查（规则3）")
    print("  ", check_unverified("这是结论：我们一定行"))
    print("  ", check_unverified("[未验证] 我猜我们行"))
    print()
    print("③ 改机制必带验收（三哥升级②）")
    print("  ", check_verification("改了真醒", False))
    print("  ", check_verification("改了身份锚", True))
    print()
    r = log_event('demo', '规则落地工具自测', 'private_rule.py')
    print("④ 留痕测试（规则7）→", r['hash'])


if __name__ == '__main__':
    main()
