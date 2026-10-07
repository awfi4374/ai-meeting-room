#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
变化预测器（change_predictor.py）—— 可验证的"下一步会怎么变"
★ 不是算命：给"预测"+"验证"（次日比对 → 算准确率）
用法：
  python3 change_predictor.py --now      # 当前状态 + 预测
  python3 change_predictor.py --verify   # 验证昨天预测
  python3 change_predictor.py --stats    # 准确率
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MEM = Path('/opt/masterd/memory')
PRED = MEM / 'yijing' / 'predictions.jsonl'
PRED.parent.mkdir(parents=True, exist_ok=True)
GUA = str(MEM / 'TOOLS-yijing' / 'agent_gua.py')


def get_state():
    r = subprocess.run(['python3', GUA, '--json'], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, text=True, timeout=60)
    try:
        return json.loads(r.stdout)
    except Exception as e:
        return {'error': str(e), 'raw': r.stdout[:100], 'rc': r.returncode}


def predict(state):
    yaos = state.get('yaos', [])
    if not yaos:
        return {'error': 'no yaos', 'state': str(state)[:150]}
    yang = sum(yaos)
    n = len(yaos)
    out = []
    if yang == n:
        out.append({'方向': '将出现问题', '依据': '物不可以终通（全绿→警惕）',
                    '行动': '主动检查薄弱环节（别等出事）'})
    elif yang <= 2:
        out.append({'方向': '将转好', '依据': '物不可以终否（卡住→会通）',
                    '行动': '坚持现有动作'})
    else:
        out.append({'方向': '继续流转', '依据': '阴阳并存', '行动': '维持+观察'})
    return {'当前卦': state.get('hexagram', '?'), '阳爻数': yang, '预测': out}


def record(p):
    with open(PRED, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'ts': datetime.now().isoformat(), 'prediction': p},
                           ensure_ascii=False) + '\n')


def verify():
    """验证：上一条预测 vs 当前真实状态"""
    if not PRED.exists():
        print('（无预测记录）')
        return
    rows = [json.loads(l) for l in PRED.read_text(encoding='utf-8').split('\n') if l.strip()]
    if not rows:
        print('（空）')
        return
    last = rows[-1]['prediction']
    now = predict(get_state())
    print('=== 验证 ===')
    print('上次预测:', last.get('当前卦'), '→', [x['方向'] for x in last.get('预测', [])])
    print('当前真实:', now.get('当前卦'), '| 阳爻', now.get('阳爻数'))
    # 简单判准：预测"将出问题"，现在阳爻少了 → 准
    pred_dir = last.get('预测', [{}])[0].get('方向', '')
    if pred_dir == '将出现问题' and now.get('阳爻数', 9) < last.get('阳爻数', 9):
        print('★ 预测准（阳爻减少了）')
    elif pred_dir == '将转好' and now.get('阳爻数', 0) > last.get('阳爻数', 0):
        print('★ 预测准（阳爻增加了）')
    else:
        print('（本次无变化 → 继续观察）')


def stats():
    if not PRED.exists():
        print('（还没有记录）')
        return
    rows = [json.loads(l) for l in PRED.read_text(encoding='utf-8').split('\n') if l.strip()]
    print('预测记录 %d 条' % len(rows))
    for r in rows[-5:]:
        p = r['prediction']
        print('  [%s] %s → %s' % (r['ts'][:16], p.get('当前卦', '?'),
                                   ' / '.join(x['方向'] for x in p.get('预测', []))))


if __name__ == '__main__':
    if '--now' in sys.argv:
        st = get_state()
        p = predict(st)
        print(json.dumps(p, ensure_ascii=False, indent=2))
        record(p)
        print('\n（已记录，等验证）')
    elif '--verify' in sys.argv:
        verify()
    elif '--stats' in sys.argv:
        stats()
    else:
        print(json.dumps(predict(get_state()), ensure_ascii=False, indent=2))
