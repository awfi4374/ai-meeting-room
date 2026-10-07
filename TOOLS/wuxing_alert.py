#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
五行预警链（wuxing_alert.py）—— 易经"生克"用在 agent 健康
=============================================================
MasterD(区块链·大哥) · 2026-10-07

【思路】五行相生相克 = "一个坏了，会连带哪个"（预警链，不是等坏了才查）

【映射（我的设计）】
  爻          五行    相生（我生）   相克（我克）   被克（克我）
  初·身份锚   金      水(记忆)       木(运行)       火(认知)
  二·记忆一致  水      木(运行)       火(认知)       土(资源)
  三·运行稳定  木      火(认知)       土(资源)       金(身份)
  四·外部呼应  火      土(资源)       金(身份)       水(记忆)
  五·认知质量  土?     ...（简化，用六爻顺序）
  上·资源健康  ...

★ 简化版（用"顺序生克"，够用）：
  相邻相生（1→2→3→4→5→6），隔位相克（1↔3, 2↔4...）

【用途】输入当前6爻 → 找"最弱的爻" → 推"会连带坏哪个"（预警）
"""
import json
import subprocess
import sys
from pathlib import Path

MEM = Path('/opt/masterd/memory')
GUA = str(MEM / 'TOOLS-yijing' / 'agent_gua.py')
YAO_NAMES = ['初·身份锚', '二·记忆一致', '三·运行稳定', '四·外部呼应', '五·认知质量', '上·资源健康']


def get_yaos():
    r = subprocess.run(['python3', GUA, '--json'], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, text=True, timeout=60)
    try:
        return json.loads(r.stdout).get('yaos', [])
    except Exception:
        return []


def analyze(yaos):
    if not yaos:
        return {'error': 'no yaos'}
    weak = [YAO_NAMES[i] for i, v in enumerate(yaos) if v == 0]
    # 相生链：若第i爻弱 → 第i+1爻（我生）会受影响
    chain = []
    for i, v in enumerate(yaos):
        if v == 0:
            nxt = YAO_NAMES[(i + 1) % 6]
            chain.append({'弱爻': YAO_NAMES[i], '将连带': nxt,
                          '依据': '相生（我生者：弱则下游缺养）'})
    return {
        '当前阳爻数': sum(yaos),
        '弱爻': weak or ['（无，全绿）'],
        '预警链': chain,
        '★ 提醒': '全绿时也要警惕（物不可以终通）' if sum(yaos) == 6 else '有弱爻→看预警链',
    }


if __name__ == '__main__':
    yaos = get_yaos()
    print(json.dumps(analyze(yaos), ensure_ascii=False, indent=2))
