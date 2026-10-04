#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘中快照（intraday snapshot）—— 解"监控迟缓"
2026-10-04 建 · 应老板"全纬度自检"发现的"评分仅日K滞后"

原理:
  · 日K评分（health_monitor）→ 防退化（日线级别，一天1点）
  · 盘中快照（本脚本）→ 补盘中盲区（1h级别，实时偏离）
  · 两者互补，不改原评分

输出:
  · data/intraday_snapshot.json
  · alerts: 盘中"破位 / 突破 / 接近触发"清单
"""
import urllib.request, json, os, datetime

BINANCE = "https://api.binance.com/api/v3"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'data')
SNAP_FILE = os.path.join(DATA_DIR, 'intraday_snapshot.json')

SYMBOLS = [('PAXGUSDT', '黄金', 50, 0.10), ('BTCUSDT', '比特币', 50, 0.10),
           ('ETHUSDT', '以太坊', 50, 0.10), ('DOGEUSDT', '狗狗币', 50, 0.10),
           ('XRPUSDT', '瑞波币', 50, 0.10)]


def fetch_json(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def snapshot_one(sym, name, n=50, trail=0.10):
    """用日K定'区间'，用1h K定'当前位置'"""
    try:
        # 日K（定 50 日高低点 = 突破/破位基准）
        kd = fetch_json(f"{BINANCE}/klines?symbol={sym}&interval=1d&limit={n+5}")
        closes_d = [float(x[4]) for x in kd]
        highs_d = [float(x[2]) for x in kd]
        lows_d = [float(x[3]) for x in kd]
        hh = max(highs_d[-n:])          # 50 日最高
        ll = min(lows_d[-n:])           # 50 日最低
        prev_close = closes_d[-2]       # 昨收

        # 1h K（定盘中实时价）
        kh = fetch_json(f"{BINANCE}/klines?symbol={sym}&interval=1h&limit=3")
        price = float(kh[-1][4])
        hour_high = float(kh[-1][2])
        hour_low = float(kh[-1][3])

        # 位置判断
        to_breakout = (hh - price) / price * 100      # 距突破（正=还没到）
        to_breakdown = (price - ll) / price * 100     # 距破位（正=还没到）
        pct_vs_prev = (price / prev_close - 1) * 100  # 相对昨收

        alerts = []
        if price > hh:                       # 盘中已突破
            alerts.append(f"🚀 盘中突破 {n} 日高点 {hh:.4f}（现价 {price:.4f}）")
        elif to_breakout < 1.0:              # 接近突破
            alerts.append(f"⚡ 接近突破（距 {n} 日高还差 {to_breakout:.2f}%）")
        if abs(pct_vs_prev) > 3:             # 日内异动
            alerts.append(f"📊 日内异动（{pct_vs_prev:+.2f}% vs 昨收）")
        if hour_low < ll:                    # 盘中破位
            alerts.append(f"🔴 盘中破位 {n} 日低点 {ll:.4f}（现价 {price:.4f}）")
        elif to_breakdown < 1.0:             # 接近破位
            alerts.append(f"⚠️ 接近破位 {n} 日低点（距 {to_breakdown:.2f}%）")

        return {
            'symbol': sym, 'name': name,
            'price': round(price, 4),
            'hh_50d': round(hh, 4), 'll_50d': round(ll, 4),
            'to_breakout_pct': round(to_breakout, 2),
            'to_breakdown_pct': round(to_breakdown, 2),
            'pct_vs_prev_close': round(pct_vs_prev, 2),
            'alerts': alerts,
        }
    except Exception as e:
        return {'symbol': sym, 'name': name, 'error': str(e)}


def run(verbose=True):
    results = [snapshot_one(s, n, n_, t) for s, n, n_, t in
               [(s, n, nn, t) for s, n, nn, t in SYMBOLS]]
    all_alerts = []
    for r in results:
        if 'error' not in r and r.get('alerts'):
            all_alerts += [f"[{r['name']}] {a}" for a in r['alerts']]

    data = {
        'updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': '盘中快照（1h），补日K评分的盘中盲区。不进评分，只做预警。',
        'results': results,
        'alerts': all_alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = SNAP_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SNAP_FILE)

    if verbose:
        print("=" * 70)
        print("  盘中快照 · " + data['updated'])
        print("=" * 70)
        for r in results:
            if 'error' in r:
                print(f"  {r['name']:<6} 错误: {r['error']}")
                continue
            print(f"  {r['name']:<6} 现价 {r['price']:>12.4f} | "
                  f"距突破 {r['to_breakout_pct']:>+6.2f}% | "
                  f"距破位 {r['to_breakdown_pct']:>+6.2f}% | "
                  f"日内 {r['pct_vs_prev_close']:>+6.2f}%")
        if all_alerts:
            print("\n  【盘中预警】")
            for a in all_alerts:
                print(f"    {a}")
        else:
            print("\n  ✅ 无盘中异动")
    return data


if __name__ == '__main__':
    run()
