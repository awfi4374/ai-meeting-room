#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""守检查（防"机制漂移"·彻查建议）
==================================================
"设一次没人守"→ 会漂 → 本模块"定期守"
"""
import os, sys, json, subprocess, datetime, stat

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
OUT = os.path.join(DATA, 'guard_check.json')
CST = datetime.timezone(datetime.timedelta(hours=8))


def run():
    issues = []
    # ① 权限（600）
    for f in ['.masterd_id.json', '.identity_pw.txt', '.bridge_token']:
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            mode = oct(os.stat(p).st_mode)[-3:]
            if mode != '600':
                issues.append('★权限 %s=%s（应600）' % (f, mode))
    # ② 单点（进程）
    for name, cmd in [('serve_safe', 'serve_safe.py'), ('guardian', 'guardian.py')]:
        r = subprocess.run(['pgrep', '-f', cmd], capture_output=True, text=True)
        if not r.stdout.strip():
            issues.append('★单点%s不在' % name)
    # ③ 数据新鲜（关键）
    import time
    for f, lim in [('health.json', 2), ('signal_state.json', 2), ('virtual_capital.json', 24)]:
        p = os.path.join(DATA, f)
        if os.path.exists(p):
            age = (time.time() - os.path.getmtime(p)) / 3600
            if age > lim:
                issues.append('数据%s %.1fh>%.0fh' % (f, age, lim))
    # ④ "不存在的"（该有但没有）
    for f in ['l1_audit.py', 'stop_fail_test.py', 'reentry_cooldown.py', 'judgment_hitrate.py']:
        if not os.path.exists(os.path.join(HERE, f)):
            issues.append('★缺%s' % f)

    out = {'ts': datetime.datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S'),
           'issues': issues, 'ok': len(issues) == 0,
           'note': '守检查（权限/单点/数据/不存在的）'}
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('守检查: %s' % ('✅ 全过' if out['ok'] else '⚠️ %d个问题' % len(issues)))
    for i in issues:
        print('  -', i)
    return out


if __name__ == '__main__':
    run()
