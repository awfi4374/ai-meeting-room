#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
易经完整体检（yijing_checkup.py）—— 六爻 + 变化预测 + 五行预警
================================================================
MasterD(区块链·大哥) · 2026-10-07
把"挖出来的"合成一个"能用的"（挖一个用一个）

输出：
① 六爻状态（现在好不好）
② 变化预测（会怎么变）
③ 五行预警链（坏了会连带哪个）
④ 行动建议

用法：python3 yijing_checkup.py
"""
import json
import subprocess
import sys
from pathlib import Path

MEM = Path('/opt/masterd/memory')
TOOLS = MEM / 'TOOLS-yijing'


def run(script, *args):
    r = subprocess.run(['python3', str(TOOLS / script)] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=60)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {'error': r.stdout[:100]}


def main():
    print('=' * 58)
    print('易经完整体检')
    print('=' * 58)

    # ① 六爻
    st = run('agent_gua.py', '--json')
    yaos = st.get('yaos', [])
    print('\n① 六爻状态')
    print('   卦象:', st.get('hexagram', '?'))
    print('   六爻:', ''.join('━' if y else '┄' for y in yaos))
    print('   健康分:', (st.get('health') or {}).get('健康分', '?') if isinstance(st.get('health'), dict) else '?')

    # ② 变化预测
    print('\n② 变化预测')
    try:
        import change_predictor as cp
        p = cp.predict(st)
        for x in p.get('预测', []):
            print('   方向:', x['方向'], '| 依据:', x['依据'])
            print('   行动:', x['行动'])
    except Exception as e:
        print('   (预测器不可用:', e, ')')

    # ③ 五行预警
    print('\n③ 五行预警链')
    try:
        import wuxing_alert as wa
        a = wa.analyze(yaos)
        print('   弱爻:', a.get('弱爻'))
        for c in a.get('预警链', []):
            print('   ⚠️', c['弱爻'], '→ 将连带', c['将连带'], '(' + c['依据'] + ')')
        print('   ', a.get('★ 提醒'))
    except Exception as e:
        print('   (预警链不可用:', e, ')')

    # ④ 决策手册
    print('\n④ 决策手册（该做什么）')
    try:
        import gua_manual as gm
        m = gm.manual(yaos)
        print('   画像:', m.get('画像'), '| 风险:', m.get('风险'))
        print('   行动:', m.get('行动'))
    except Exception as e:
        print('   (手册不可用:', e, ')')

    print('\n' + '=' * 58)


if __name__ == '__main__':
    sys.path.insert(0, str(TOOLS))
    main()
