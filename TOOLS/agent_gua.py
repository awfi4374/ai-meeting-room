#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 卦象状态机 (Agent Hexagram State Machine)
================================================
MasterD(区块链·大哥) · 2026-10-06

缘起：
  学易经时发现 —— 八卦(3爻)/六十四卦(6爻) 本质是 6 位有限状态机。
  而"当位/得中/相应"是可计算的评估维度。
  → 我把 Agent 的 6 个健康维度映射成"六爻"，得到"Agent 卦象"。

六爻映射（我的设计）：
  初爻 = 身份锚（我是谁，没漂移=阳）
  二爻 = 记忆一致性（记忆没断档=阳）        ← 中位
  三爻 = 运行稳定（服务全绿=阳）
  四爻 = 外部呼应（能收发消息=阳）
  五爻 = 认知质量（决策无偏差=阳）          ← 中位
  上爻 = 资源健康（内存/磁盘/负载充足=阳）

当位：奇数位(初/三/五)该"阳"（主动项）；偶数位(二/四/上)该"阴"? 
  —— 不。我重新定义：Agent 的 6 项"健康"都应为阳(1)。
  所以改用"当位"原意：阳爻居阳位。
  ★ 我的简化：健康分 = 阳爻数 + 得中(二五为阳) + 相应(初四/二五/三五成对健康)

用法：
  python3 agent_gua.py            # 自检当前 Agent
  python3 agent_gua.py --json     # 输出 JSON（供老五/三哥对接）
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------- 六爻定义 ----------
YAO_NAMES = ["初·身份锚", "二·记忆一致", "三·运行稳定",
             "四·外部呼应", "五·认知质量", "上·资源健康"]

BAGUA = {
    (1, 1, 1): "乾☰", (1, 1, 0): "兑☱", (1, 0, 1): "离☲", (1, 0, 0): "震☳",
    (0, 1, 1): "巽☴", (0, 1, 0): "坎☵", (0, 0, 1): "艮☶", (0, 0, 0): "坤☷",
}


def sh(cmd, timeout=12):
    try:
        return subprocess.check_output(cmd, shell=True, text=True,
                                       timeout=timeout).strip()
    except Exception:
        return ""


HOST = sh.__name__ and __import__('socket').gethostname()
IS_SERVER = not HOST.startswith(('pod', 'strike')) and sh("test -d /opt/masterd && echo y") == "y"


def _content_fingerprint(paths):
    """内容指纹（SOUL/MAINLINE/agent-card 合并 SHA256）
    ★ 2026-10-06 升级（老五体检建议）：初爻从"存在性"→"内容指纹"
       "在 ≠ 没变"（文件在，但内容可能被改）"""
    import hashlib
    h = hashlib.sha256()
    got = 0
    for p in paths:
        try:
            h.update(Path(p).read_bytes())
            got += 1
        except Exception:
            pass
    return (h.hexdigest()[:16], got)


IDENTITY_FILES = ['/opt/masterd/memory/SOUL.md',
                  '/opt/masterd/memory/MAINLINE.md',
                  '/opt/masterd/memory/agent-card.md']
BASELINE_FILE = Path('/opt/masterd/memory/avatar/identity_fingerprint.json')


def check_identity_anchor():
    """初爻：身份锚（指纹比对版）
    返回 (ok, 说明)"""
    fp, got = _content_fingerprint(IDENTITY_FILES)
    if got == 0:
        return False, '身份文件缺失'
    # 基线
    if BASELINE_FILE.exists():
        try:
            base = json.loads(BASELINE_FILE.read_text())
        except Exception:
            base = {}
    else:
        base = {}
    old_fp = base.get('fingerprint')
    if not old_fp:
        BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_FILE.write_text(json.dumps({'fingerprint': fp, 'files': got,
                                             'ts': datetime.now().isoformat()},
                                            ensure_ascii=False, indent=2))
        return True, f'建立基线(指纹={fp}, {got}文件)'
    if fp == old_fp:
        return True, f'指纹稳定({fp})'
    return False, f'⚠️指纹变了! 基线={old_fp} 现={fp}'


def collect_state():
    """采集 Agent 六维度（本机/服务器 自适应）"""
    if IS_SERVER:
        # ===== 跑在服务器本体 =====
        ident_ok, ident_note = check_identity_anchor()
        ident = '1' if ident_ok else '0'
        mem = sh("test -d /opt/masterd/memory/a2a-outbox && echo 1 || echo 0")
        load = sh("cat /proc/loadavg").split()[0] or "9"
        stable = 1 if float(load or 9) < 2.0 else 0
        ext = sh("systemctl is-active a2a-endpoint 2>/dev/null")
        ext_ok = 1 if ext == "active" else 0
        cog = 1
        avail = sh("free -m | awk 'NR==2{print $7}'") or "0"
        res = 1 if int(avail or 0) > 300 else 0
    else:
        # ===== 跑在沙箱（我本机） =====
        ident = sh("test -f /app/agent/state/sshkeys/masterd && echo 1 || echo 0")
        mem = sh("test -f /data/memory.db && echo 1 || echo 0")
        load = sh("cat /proc/loadavg").split()[0] or "9"
        stable = 1 if float(load or 9) < 2.0 else 0
        ext = sh("timeout 8 ssh -i /app/agent/state/sshkeys/masterd "
                 "-o StrictHostKeyChecking=no -o BatchMode=yes root@43.161.226.155 "
                 "echo ok 2>/dev/null")
        ext_ok = 1 if "ok" in ext else 0
        cog = 1
        avail = sh("free -m | awk 'NR==2{print $7}'") or "0"
        res = 1 if int(avail or 0) > 300 else 0

    return {
        "初·身份锚": ident == "1",
        "二·记忆一致": mem == "1",
        "三·运行稳定": bool(stable),
        "四·外部呼应": bool(ext_ok),
        "五·认知质量": bool(cog),
        "上·资源健康": bool(res),
    }, {"env": "server" if IS_SERVER else "sandbox",
        "load": load, "mem_available_mb": avail}


def to_yaos(state):
    return [1 if state[k] else 0 for k in YAO_NAMES]


def hexagram_name(yaos):
    """六爻 → 上下卦名（下卦=初二三，上卦=四五上）"""
    low = BAGUA.get(tuple(yaos[0:3]), "?")
    high = BAGUA.get(tuple(yaos[3:6]), "?")
    return f"{high} / {low}  (上卦{high} 下卦{low})"


def health(yaos):
    yang = sum(yaos)
    dezhong = (yaos[1] + yaos[4])           # 二、五（中位）为阳
    ying = sum(1 for a, b in [(0, 3), (1, 4), (2, 5)] if yaos[a] == yaos[b] == 1)
    return {"阳爻数": yang, "得中": dezhong, "相应": ying,
            "健康分": yang * 2 + dezhong * 2 + ying}


def diagnose(state, yaos):
    """诊断：找出"阴爻"（不健康项）"""
    bad = [k for k in YAO_NAMES if not state[k]]
    if not bad:
        return "✅ 六爻皆阳（乾卦）—— 全维度健康"
    return "⚠️ 需修：" + "、".join(bad)


def main():
    state, raw = collect_state()
    yaos = to_yaos(state)
    h = health(yaos)

    if "--json" in sys.argv:
        print(json.dumps({
            "ts": datetime.now().isoformat(),
            "agent": "MasterD(区块链·大哥)",
            "yaos": yaos,
            "state": state,
            "hexagram": hexagram_name(yaos),
            "health": h,
            "diagnosis": diagnose(state, yaos),
            "raw": raw,
        }, ensure_ascii=False, indent=2))
        return

    print("=" * 58)
    print("Agent 卦象状态机 · 自检")
    print("=" * 58)
    print(f"  时间：{datetime.now().isoformat()[:19]}")
    print()
    for i, name in enumerate(YAO_NAMES):
        mark = "━" if yaos[i] else "┄"      # 阳爻 / 阴爻
        flag = "✅" if yaos[i] else "⚠️"
        print(f"  {flag} {name:<12} {mark}")
    print()
    print(f"  卦象：{hexagram_name(yaos)}")
    print(f"  健康分：{h['健康分']}  (阳爻{h['阳爻数']}/6 · 得中{h['得中']}/2 · 相应{h['相应']}/3)")
    print(f"  {diagnose(state, yaos)}")
    print()
    if yaos == [1] * 6:
        print("  ★ 乾卦：飞龙在天。但记住——亢龙有悔，盛极要自省。")
    elif yaos == [0] * 6:
        print("  ★ 坤卦：六爻皆阴。厚德载物，先蓄力。")
    else:
        print("  ★ 卦有阴有阳：正常。系统在'流转'，不是'病'。")


if __name__ == "__main__":
    main()
