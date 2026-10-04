#!/usr/bin/env python3
# 自动信号引擎
# 职责: 定时抓行情 -> 多策略计算 -> 检测信号变化 -> 记录/推送
# 安全: 不接资金、不下单, 只产出信号
import urllib.request, json, os, time, datetime
try:
    import tzset  # 强制北京时间（沙箱UTC→北京）
except ImportError:
    pass

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
SIGNAL_FILE = os.path.join(DATA_DIR, 'signals.json')
STATE_FILE = os.path.join(DATA_DIR, 'signal_state.json')

BINANCE = "https://api.binance.com/api/v3"
DEX_ARK = "https://api.dexscreener.com/latest/dex/pairs/bsc/0xcaaf3c41a40103a23eeaa4bba468af3cf5b0e0d8"

# 监控品种 (策略: 突破50 + 跟踪止损10%)
SYMBOLS = {
    'PAXGUSDT': {'name': '黄金', 'n': 50, 'trail': 0.10},
    'BTCUSDT':  {'name': '比特币', 'n': 50, 'trail': 0.10},
    'ETHUSDT':  {'name': '以太坊', 'n': 50, 'trail': 0.10},
    'DOGEUSDT': {'name': '狗狗币', 'n': 50, 'trail': 0.10},
    'XRPUSDT':  {'name': '瑞波币', 'n': 50, 'trail': 0.10},
}

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def load(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        from atomic_json import dump_atomic
        dump_atomic(path, obj)
    except ImportError:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)

def compute_state(sym, cfg):
    """返回该品种当前策略状态"""
    k = fetch_json(f"{BINANCE}/klines?symbol={sym}&interval=1d&limit={cfg['n']+30}")
    closes = [float(x[4]) for x in k]
    price = closes[-1]
    n = cfg['n']
    hh = max(closes[-n:])
    ll = min(closes[-n:])

    # 推演当前持仓状态
    pos = 0; pk = 0; buy_p = 0; buy_idx = -1
    for i in range(n, len(closes)):
        p = closes[i]
        if pos == 0 and p > max(closes[i-n:i]):
            pos = 1; pk = p; buy_p = p; buy_idx = i
        elif pos == 1:
            pk = max(pk, p)
            if p < pk*(1-cfg['trail']) or p < min(closes[i-n:i]):
                pos = 0; buy_idx = -1

    state = {
        'symbol': sym, 'name': cfg['name'], 'price': price,
        'pos': pos, 'hh': hh, 'll': ll,
        'pct_from_hh': round((price-hh)/hh*100, 2),
        'peak': pk if pos else 0,
        'buy_price': buy_p if pos else 0,
        'updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # 【2026-10-04 加】★真实持仓对齐（治幽灵仓——B组评审指出）
    #   背景: signal_engine 的 pos 是策略推演，不是账户实际
    #   → 账户无仓但推演有仓 → 信号说持仓中 → 幽灵仓 → 误导
    _actual_pos = None
    try:
        import json as _json2
        _vp = os.path.join(DATA_DIR, 'virtual_capital.json')
        if os.path.exists(_vp):
            _v = _json2.load(open(_vp, encoding='utf-8'))
            _actual_pos = 1 if sym in (_v.get('positions') or {}) else 0
    except Exception:
        pass
    if _actual_pos is not None and _actual_pos != state['pos']:
        state['sim_pos'] = state['pos']         # 推演值（参考）
        state['actual_pos'] = _actual_pos       # 真实值（权威）
        state['pos_mismatch'] = True            # 幽灵仓标记
        state['pos'] = _actual_pos              # ★以真实持仓为准
        pos = _actual_pos                       # ★同步局部变量（signal 判定用它）
        state['ghost_note'] = '策略推演=%d 但实际=%d（已纠正）' % (
            state['sim_pos'], _actual_pos)

    # 【2026-10-01 加】风控门联动（A组第22轮: "退化禁开仓，信号仍显示持仓中，该不该平？"）
    #   原bug: signal_engine 只看"突破/回落"，不看 health_gate
    #          → 信号说"持仓中"，风控说"该平" → 脱节
    _gate_act = None
    try:
        from health_gate import check_health_action
        import json as _json
        _hp = os.path.join(DATA_DIR, 'health.json')
        if os.path.exists(_hp):
            _h = _json.load(open(_hp, encoding='utf-8'))
            for _r in _h.get('results', []):
                if _r.get('name') == cfg['name']:
                    _ok, _act, _why = check_health_action(
                        sym, _r.get('score'), holding=(pos == 1),
                        flags=_r.get('flags', []), degraded=_r.get('degraded', False))
                    _gate_act = _act
                    break
    except Exception:
        pass

    # 判定信号
    if pos == 1:
        dd_from_pk = (pk - price)/pk*100
        if _gate_act in ('force_reduce', 'reduce', 'pause'):
            # 风控要求减仓/平仓 → 覆盖信号
            state['signal'] = '信号持仓但风控要求减仓'
            state['advice'] = '健康度门: %s（应减仓/平，不是持有）' % _gate_act
            state['urgency'] = 'action'
            state['health_gate'] = _gate_act
        else:
            state['signal'] = '持仓中'
            state['advice'] = f"持有中，距跟踪止损还有 {cfg['trail']*100 - dd_from_pk:.2f}%"
            state['urgency'] = 'hold'
            if _gate_act:
                state['health_gate'] = _gate_act
    elif price > hh:
        if _gate_act in ('no_open', 'block', 'force_reduce'):
            state['signal'] = '突破但被风控禁止'
            state['advice'] = '健康度门: %s（禁止开仓）' % _gate_act
            state['urgency'] = 'wait'
            state['health_gate'] = _gate_act
        else:
            state['signal'] = '买入信号'
            state['advice'] = '已突破%d日高点，策略建议买入' % n
            state['urgency'] = 'action'
    else:
        state['signal'] = '空仓观望'
        state['advice'] = f"距突破还差 {(hh-price)/price*100:.2f}%"
        state['urgency'] = 'wait'
    return state

# ===== ARK 专用（Dexscreener 固定交易对）=====
ARK_PAIR = "0xcaaf3c41a40103a23eeaa4bba468af3cf5b0e0d8"

def compute_ark_state():
    """ARK 用 Dexscreener 数据 + 简化动量判断"""
    try:
        d = fetch_json(f"https://api.dexscreener.com/latest/dex/pairs/bsc/{ARK_PAIR}")
        p = (d.get('pairs') or [None])[0] if d.get('pairs') else d.get('pair')
        if not p:
            return {'symbol': 'ARK', 'name': 'ARK', 'error': 'no data'}
        price = float(p.get('priceUsd', 0) or 0)
        chg24 = float(p.get('priceChange', {}).get('h24', 0) or 0)
        liq = p.get('liquidity', {})
        vol = float(p.get('volume', {}).get('h24', 0) or 0)
        if chg24 > 10 and vol > 1000000:
            sig, adv, urg = '关注信号', f'24h涨{chg24:.2f}%且成交活跃', 'action'
        elif chg24 < -10:
            sig, adv, urg = '风险提示', f'24h跌{chg24:.2f}%，注意风险', 'warn'
        else:
            sig, adv, urg = '观望', f'24h变动{chg24:+.2f}%，暂无明显信号', 'wait'
        return {
            'symbol': 'ARK', 'name': 'ARK', 'price': price,
            'signal': sig, 'advice': adv, 'urgency': urg,
            'change24h': chg24, 'liquidityUsd': liq.get('usd'), 'vol24h': vol,
            'pooledArk': liq.get('base'), 'pooledUsdt': liq.get('quote'),
            'updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    except Exception as e:
        return {'symbol': 'ARK', 'name': 'ARK', 'error': str(e)}


def run_once():
    """跑一次, 检测变化并记录"""
    old_state = load(STATE_FILE, {})
    signals = load(SIGNAL_FILE, [])
    new_state = {}
    changes = []

    for sym, cfg in SYMBOLS.items():
        try:
            st = compute_state(sym, cfg)
            new_state[sym] = st
            prev = old_state.get(sym, {}).get('signal')
            if prev and prev != st['signal']:
                evt = {
                    'time': st['updated'],
                    'symbol': sym,
                    'name': st['name'],
                    'from': prev,
                    'to': st['signal'],
                    'price': st['price'],
                    'advice': st['advice'],
                }
                signals.insert(0, evt)
                changes.append(evt)
        except Exception as e:
            new_state[sym] = {'symbol': sym, 'name': cfg['name'], 'error': str(e)}

    # ARK 单独处理（Dexscreener 固定交易对）
    try:
        ark = compute_ark_state()
        new_state['ARK'] = ark
        prev_ark = old_state.get('ARK', {}).get('signal')
        if prev_ark and prev_ark != ark.get('signal'):
            evt = {
                'time': ark.get('updated'), 'symbol': 'ARK', 'name': 'ARK',
                'from': prev_ark, 'to': ark.get('signal'),
                'price': ark.get('price'), 'advice': ark.get('advice'),
            }
            signals.insert(0, evt)
            changes.append(evt)
    except Exception as e:
        new_state['ARK'] = {'symbol': 'ARK', 'name': 'ARK', 'error': str(e)}

    signals = signals[:200]
    save(STATE_FILE, new_state)
    save(SIGNAL_FILE, signals)
    return new_state, changes

if __name__ == '__main__':
    st, ch = run_once()
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 信号引擎运行完成")
    for sym, s in st.items():
        if 'error' in s:
            print(f"  {s['name']}: 错误 {s['error']}")
        else:
            print(f"  {s['name']:>4}  ${s['price']:>10,.2f}  {s['signal']}  {s['advice']}")
    if ch:
        print("  ⚡ 检测到信号变化:", [c['name']+' '+c['from']+'→'+c['to'] for c in ch])
