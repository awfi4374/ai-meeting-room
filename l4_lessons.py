#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L4 教训层（单笔复盘 → 规则）
==================================================
来源: B组第98轮"缺哪层"
  "缺 L4（教训层）→ DOGE/XRP 各亏7%，系统不会追问'同簇双亏'"

【做法】自动复盘: 每笔平仓 → 生成教训
"""
import os, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
LESSONS = os.path.join(DATA, 'l4_lessons.jsonl')
CST = datetime.timezone(datetime.timedelta(hours=8))


def review_closed_trades():
    """复盘所有平仓交易 → 生成教训"""
    try:
        d = json.load(open(os.path.join(DATA, 'virtual_trades.json'), encoding='utf-8'))
    except Exception:
        return []
    trades = d.get('trades', [])
    sells = [t for t in trades if t.get('action') == 'SELL']
    # 读已复盘（防重复）
    done = set()
    if os.path.exists(LESSONS):
        for line in open(LESSONS, encoding='utf-8'):
            try:
                done.add(json.loads(line).get('key'))
            except Exception:
                pass
    new = []
    for s in sells:
        key = '%s|%s|%s' % (s.get('date'), s.get('symbol'), s.get('reason', '')[:20])
        if key in done:
            continue
        pnl = s.get('pnl', 0)
        lesson = {
            'key': key, 'ts': datetime.datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S'),
            'date': s.get('date'), 'symbol': s.get('symbol'), 'name': s.get('name'),
            'pnl': pnl, 'reason': s.get('reason', ''),
            'lesson': ('亏损(%.2f): %s' % (pnl, s.get('reason', '')) if pnl < 0
                       else '盈利(%.2f)' % pnl),
        }
        new.append(lesson)
        with open(LESSONS, 'a', encoding='utf-8') as f:
            f.write(json.dumps(lesson, ensure_ascii=False) + '\n')
    return new


def analyze_patterns():
    """找"重复模式"（B组: 同簇双亏）"""
    if not os.path.exists(LESSONS):
        return []
    rows = []
    for line in open(LESSONS, encoding='utf-8'):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    losses = [r for r in rows if r.get('pnl', 0) < 0]
    # 按"日期"聚类（同一天多笔亏损 → 同簇）
    by_date = {}
    for r in losses:
        by_date.setdefault(r['date'], []).append(r['name'])
    patterns = []
    for d, names in by_date.items():
        if len(names) >= 2:
            patterns.append('同一天多笔亏损（%s）: %s' % (d, ', '.join(names)))
    return patterns


if __name__ == '__main__':
    new = review_closed_trades()
    print("新复盘: %d 笔" % len(new))
    for n in new:
        print("  %s" % n['lesson'])
    pats = analyze_patterns()
    if pats:
        print("模式:")
        for p in pats:
            print("  🔴 %s" % p)


def to_rules(pattern):
    """★教训→规则（2026-10-05 加，应B组"教训不沉淀为规则"）
    把"重复模式"转成"可执行规则"（写进 l4_rules.json）
    """
    import json as _j
    RULES = os.path.join(DATA, 'l4_rules.json')
    rules = []
    if os.path.exists(RULES):
        try:
            rules = _j.load(open(RULES, encoding='utf-8')).get('rules', [])
        except Exception:
            rules = []

    new_rules = []
    # 规则1: 同簇双亏 → 同簇同向限1仓
    if '同一天多笔亏损' in pattern:
        r = {
            'id': 'R1_cluster_single_bet',
            'trigger': '同一簇（加密）同向持多仓',
            'rule': '同簇同向最多1仓（防伪分散）',
            'source': pattern,
            'created': datetime.datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S'),
        }
        if not any(x.get('id') == r['id'] for x in rules):
            rules.append(r)
            new_rules.append(r)

    if new_rules:
        _j.dump({'rules': rules}, open(RULES, 'w', encoding='utf-8'),
                ensure_ascii=False, indent=1)
    return new_rules


def apply_rules():
    """读规则 + 检查当前持仓是否违规"""
    import json as _j
    RULES = os.path.join(DATA, 'l4_rules.json')
    if not os.path.exists(RULES):
        return []
    try:
        rules = _j.load(open(RULES, encoding='utf-8')).get('rules', [])
    except Exception:
        return []
    violations = []
    try:
        vc = _j.load(open(os.path.join(DATA, 'virtual_capital.json'), encoding='utf-8'))
        positions = vc.get('positions', {})
        # 规则R1: 同簇（加密）同向限1仓
        crypto = [s for s in positions if s in ('BTCUSDT', 'ETHUSDT', 'DOGEUSDT', 'XRPUSDT')]
        if len(crypto) > 1:
            violations.append('R1违规: 同簇持多仓 %s（应≤1）' % crypto)
    except Exception:
        pass
    return violations
