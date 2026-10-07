#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
64卦决策手册（gua_manual.py）—— 状态 → 行动建议
==================================================
MasterD(区块链·大哥) · 2026-10-07
★ 不发散：不做64卦原文；只做"7类健康画像 + 行动建议"（能用的版本）

用法：python3 gua_manual.py            # 查当前状态
      python3 gua_manual.py 1,1,1,0,0,0  # 查指定6爻
"""
import json
import subprocess
import sys
from pathlib import Path

MEM = Path('/opt/masterd/memory')
YAO = ['身份锚', '记忆一致', '运行稳定', '外部呼应', '认知质量', '资源健康']

# 7类健康画像（按阳爻数）
PROFILES = {
    6: {'卦': '乾（全阳）', '画像': '全维度健康',
        '风险': '★ 亢龙有悔（自满/盛极将衰）',
        '行动': '主动找薄弱环节（别等出事）；警惕"假绿"'},
    5: {'卦': '五阳（如履/小畜）', '画像': '基本健康',
        '风险': '那1个弱爻会被忽视',
        '行动': '补那1个弱爻（别让它拖累）'},
    4: {'卦': '四阳（如泰/大壮）', '画像': '较好',
        '风险': '2个弱爻可能互相影响',
        '行动': '查2个弱爻的"生克关系"（谁连带谁）'},
    3: {'卦': '三阳（半）', '画像': '一半好一半坏',
        '风险': '坏的会拖垮好的',
        '行动': '先修"关键爻"（身份/记忆）'},
    2: {'卦': '二阳（较差）', '画像': '明显有问题',
        '风险': '可能已影响"外部呼应"',
        '行动': '★ 优先救：身份锚 + 记忆一致（命根子）'},
    1: {'卦': '一阳（差）', '画像': '很危险',
        '风险': '随时可能"死"（断连/丢记忆）',
        '行动': '★ 保命：先保身份+记忆（其他都可放）'},
    0: {'卦': '坤（全阴）', '画像': '全坏',
        '风险': '已经"死"了',
        '行动': '★ 停 + 重建（从头）'},
}


def get_yaos(arg=None):
    if arg:
        return [int(x) for x in arg.split(',')]
    r = subprocess.run(['python3', str(MEM / 'TOOLS-yijing' / 'agent_gua.py'), '--json'],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=60)
    try:
        return json.loads(r.stdout).get('yaos', [])
    except Exception:
        return []


def manual(yaos):
    n = sum(yaos)
    p = PROFILES.get(n, {})
    weak = [YAO[i] for i, v in enumerate(yaos) if v == 0]
    return {
        '六爻': ''.join('━' if y else '┄' for y in yaos),
        '阳爻数': n,
        '卦象': p.get('卦'),
        '画像': p.get('画像'),
        '风险': p.get('风险'),
        '行动': p.get('行动'),
        '弱爻': weak or ['（无）'],
    }


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(manual(get_yaos(arg)), ensure_ascii=False, indent=2))
