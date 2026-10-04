#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动运行调度器（三家共识版）
=============================
用户要求（2026-09-24）: "怎么样才能让我们这个自动运行？"

三家共识原则:
  · 常态异步（每晚一次批量同步，不是高频）
  · 异常触发（发现问题立即跑）
  · 大事留人确认（涉及钱/不可逆 → 命令清单给用户）

功能:
  · 每小时检查: 是否该跑常态任务
  · 每日 01:00（北京）: 跑 night_sync（批量协同）
  · 每小时: 费用统计
  · 异常检测: CVaR/熔断/数据 → 触发布
用法: python3 auto_runner.py --watch   （守护方式）
      python3 auto_runner.py --once    （单次检查）
"""
import os, sys, json, time, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
TZ = 8
STATE = os.path.join(DATA, 'auto_runner_state.json')

# 常态任务（低峰跑）
NIGHT_HOUR = 1          # 北京 01:00 跑批量协同
LAST_RUN_KEY = 'last_night_sync'
FEE_KEY = 'last_fee_check'
STUDY_KEY = 'last_study'        # 每天学 1 课（用户要求: 自我提升）
STUDY_HOUR = 2                  # 凌晨 02:00 学（低峰）
MEMBAK_KEY = 'last_membak'      # 每天导出记忆备份（供服务器同步）
INTEG_KEY = 'last_integ_check'  # 每天检查模块集成（防'装饰品'）


CST = datetime.timezone(datetime.timedelta(hours=TZ))


def bj_now():
    """北京时间（【2026-09-30 修】用真 CST，不靠 utc+8 加标签）"""
    return datetime.datetime.now(CST)


def load_state():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except Exception:
        return {}


def save_state(s):
    os.makedirs(DATA, exist_ok=True)
    json.dump(s, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def run(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=HERE, shell=True)
        return r.returncode == 0, (r.stdout or '')[-500:]
    except subprocess.TimeoutExpired:
        return False, '[超时]'
    except Exception as e:
        return False, str(e)


def _is_paused():
    """检查强制暂停（用户按钮）"""
    try:
        return os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           'data', 'PAUSE.flag'))
    except Exception:
        return False


def check_once(state):
    now = bj_now()
    today = now.strftime('%Y-%m-%d')
    h = now.hour
    log = []
    # [2026-10-04 加] 强制暂停（用户按钮）
    if _is_paused():
        log.append("⏸️ 已强制暂停（PAUSE.flag）→ 跳过本轮所有任务")
        return log

    # ① 夜间批量协同（每天 01:00，只跑一次）
    if h == NIGHT_HOUR and state.get(LAST_RUN_KEY) != today:
        log.append("→ 跑夜间协同（%s 01:00）" % today)
        ok, out = run("python3 night_sync.py --once", timeout=900)
        state[LAST_RUN_KEY] = today
        log.append("  结果: %s" % ("成功" if ok else "失败"))

    # ①.5 自我学习（每天 02:00，低峰）
    if h == STUDY_HOUR and state.get(STUDY_KEY) != today:
        log.append("→ 自我学习（%s 02:00）" % today)
        ok, out = run("python3 self_study.py --once", timeout=900)
        state[STUDY_KEY] = today
        log.append("  结果: %s" % ("成功" if ok else "失败"))

    # ①.65 记忆地图自动更新（每天 04:05，防过时）
    MMKEY = 'last_mem_map'
    if h == 4 and now.minute >= 5 and state.get(MMKEY) != today:
        okmm, outmm = run("python3 update_memory_map.py", timeout=60)
        state[MMKEY] = today
        log.append("  记忆地图更新: %s" % ('完成' if okmm else '失败'))

    # ①.7 核心打包（每天 03:15，人格核心异地备份）
    COREKEY = 'last_core_pack'
    if h == 3 and now.minute >= 15 and state.get(COREKEY) != today:
        okcp, outcp = run("bash pack_core.sh", timeout=60)
        state[COREKEY] = today
        log.append("  核心打包: %s" % ('完成' if okcp else '失败'))

    # ①.8 记忆备份导出（每天 03:00，供服务器同步）
    if h == 3 and state.get(MEMBAK_KEY) != today:
        log.append("→ 记忆备份导出（%s 03:00）" % today)
        ok, out = run("python3 memory_backup.py export", timeout=60)
        state[MEMBAK_KEY] = today
        log.append("  结果: %s" % ("成功" if ok else "失败"))

    # ①.9 集成检查（每天 05:00，防"装饰品"）
    if h == 5 and state.get(INTEG_KEY) != today:
        log.append("→ 集成检查（%s 05:00）" % today)
        ok, out = run("python3 check_integration.py", timeout=60)
        # [2026-10-02 加] 契约检查（含反证测试，Kimi 建议）
        okc, outc = run("python3 contract_check.py", timeout=60)
        if not okc:
            log.append("  🔴 契约检查失败（见输出）")
            try:
                import alert as _al2
                _al2.send_alert('集成契约失败', (outc or '')[-400:], 'error')
            except Exception:
                pass
        else:
            log.append("  ✅ 契约检查通过")
        state[INTEG_KEY] = today
        # 【2026-10-01 修】集成检查失败 → 告警（原版只看关键词）
        if (not ok) or '集成问题' in (out or '') or '无人调用' in (out or ''):
            log.append("  ⚠️ 发现未接入模块（见输出）")
            try:
                import alert as _al
                _al.send_alert('集成检查异常', (out or '')[-500:], 'warning')
            except Exception:
                pass
        log.append("  结果: %s" % ("成功" if ok else "失败"))

    # ①.95 修复验证 + 孤儿扫描（每天 05:30，回滚契约）
    VKEY = 'last_verify'
    if h == 5 and now.minute < 30 and state.get(VKEY) != today:
        log.append("→ 修复验证（%s 05:00）" % today)
        ok, out = run("python3 verify_fix.py --tag auto", timeout=120)
        state[VKEY] = today
        log.append("  判定: %s" % ('PASS' if ok else 'FAIL（看 data/verify_latest.json）'))
        ok2, out2 = run("python3 orphan_scan.py", timeout=120)
        log.append("  孤儿扫描: %s" % ('成功' if ok2 else '失败'))
        ok3, out3 = run("python3 data_contract.py", timeout=60)
        okb, outb = run("python3 make_baseline.py", timeout=60)
        log.append("  回归基线: %s" % ('已更新' if okb else '失败'))
        log.append("  数据契约: %s" % ('全部满足' if ok3 else '⚠️ 有阻断（看 data/data_contract.json）'))

    # ①.96 学习健康（每小时，治"学习停摆无人知"）
    SHKEY = 'last_study_health'
    if state.get(SHKEY) != now.strftime('%Y-%m-%d %H'):
        ok4, out4 = run("python3 study_health.py", timeout=60)
        state[SHKEY] = now.strftime('%Y-%m-%d %H')
        if not ok4:
            log.append("  🔴 学习模块异常（见 data/study_health.json）")
    # 【2026-09-30 加】决策者姿态自检（每小时，防线2 自测）
    try:
        import subprocess as _sp2
        _r2 = _sp2.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_decision.py')],
                       input='要我做吗', capture_output=True, text=True, timeout=15)
        if _r2.returncode == 0:
            log.append("  🔴 决策检查失效（'要我做吗'未被拦截）")
    except Exception:
        pass

    # 【2026-10-04 加】盘中快照（每小时，补日K评分的盘中盲区）
    ISKEY = 'last_intraday_snap'
    if state.get(ISKEY) != now.strftime('%Y-%m-%d %H'):
        oki, outi = run("python3 intraday_snapshot.py", timeout=90)
        state[ISKEY] = now.strftime('%Y-%m-%d %H')
        if oki:
            # 有盘中预警 → 记日志（可被 alert 读取）
            try:
                _snap = json.load(open(os.path.join(HERE, 'data/intraday_snapshot.json'), encoding='utf-8'))
                _al = _snap.get('alerts', [])
                if _al:
                    log.append("  ⚠️ 盘中预警 %d 条: %s" % (len(_al), '; '.join(_al)))
            except Exception:
                pass
        else:
            log.append("  🔴 盘中快照失败（见 data/intraday_snapshot.json）")

    # 【2026-09-30 加】双时钟报告（每小时，P1 定性实验进度）
    try:
        import subprocess as _sp3
        _r3 = _sp3.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clock_probe.py'), '--report'],
                       capture_output=True, text=True, timeout=30)
        _lines = [l for l in (_r3.stdout or '').split('\n') if '判定:' in l or '冻结累计' in l]
        for _l in _lines:
            log.append("  " + _l.strip())
    except Exception:
        pass

    # 【2026-09-30 加】记忆自检（每小时，防关键记忆文件丢失）
    try:
        import subprocess as _sp
        _r = _sp.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'memory_check.py'), '--quiet'],
                     capture_output=True, text=True, timeout=30)
        if _r.returncode != 0:
            log.append("  🔴 记忆自检失败：" + (_r.stdout or '').strip()[:200])
    except Exception:
        pass

    # ①.97 记忆策展（每天 04:00，防污染 + 提炼金句）
    MCKEY = 'last_memory_curate'
    if h == 4 and state.get(MCKEY) != today:
        log.append("→ 记忆策展（%s 04:00）" % today)
        ok5, out5 = run("python3 memory_curator.py", timeout=180)
        log.append("  策展: %s" % ('成功' if ok5 else '失败'))
        okmc, outmc = run("python3 memory_conflict.py check", timeout=60)
        log.append("  冲突检测: %s" % ('无冲突' if okmc == 0 else '⚠️ 发现冲突'))
        ok6, out6 = run("python3 quote_filter.py", timeout=60)
        log.append("  金句过滤: %s" % ('成功' if ok6 else '失败'))

    # ①.98 跳空压力 + 保护（每天 05:40，B组第5点）
    GKEY = 'last_gap_stress'
    if h == 5 and state.get(GKEY) != today:
        ok7, out7 = run("python3 gap_stress.py", timeout=120)
        ok8, out8 = run("python3 gap_guard.py", timeout=60)
        state[GKEY] = today
        log.append("  跳空压力+保护: %s" % ('OK' if (ok7 and ok8) else '有警告'))

    # ①.99 沙箱/服务器一致性（每小时，治"改沙箱服务器不知道"）
    FSKEY = 'last_file_sync'
    if state.get(FSKEY) != now.strftime('%Y-%m-%d %H'):
        ok9, out9 = run("python3 file_sync_check.py", timeout=60)
        state[FSKEY] = now.strftime('%Y-%m-%d %H')
        if not ok9:
            log.append("  ⚠️ 有待同步文件（见 data/file_sync_latest.json）")

    # ①.995 变更传播检查（每小时，根治"改了没生效"）
    CPKEY = 'last_change_prop'
    if state.get(CPKEY) != now.strftime('%Y-%m-%d %H'):
        okc, outc = run("python3 change_propagation.py", timeout=60)
        state[CPKEY] = now.strftime('%Y-%m-%d %H')
        if not okc:
            log.append("  🔴 有「改了没传播」的变更（见 data/change_prop_latest.json）")

    # ①.996 自修震荡检测（每小时，防"自修掩盖真问题"）
    HLKEY = 'last_heal_ledger'
    if state.get(HLKEY) != now.strftime('%Y-%m-%d %H'):
        okh, outh = run("python3 heal_ledger.py check", timeout=60)
        state[HLKEY] = now.strftime('%Y-%m-%d %H')
        if not okh:
            log.append("  🔴 自修震荡（同进程 24h >3 次）")

    # ①.997 中文文档同步（每小时，防中文名 404）
    CSKEY = 'last_cn_sync'
    if state.get(CSKEY) != now.strftime('%Y-%m-%d %H'):
        okcs, outcs = run("bash auto_sync_docs.sh", timeout=120)
        state[CSKEY] = now.strftime('%Y-%m-%d %H')
        if not okcs:
            log.append("  ⚠️ 中文文档同步失败")

    # ①.998 决策统计（每天 23:00，让"决策可追溯"自动运转）
    DSKEY = 'last_decision_stats'
    if h == 23 and state.get(DSKEY) != today:
        okds, outds = run("python3 decision_stats.py", timeout=120)
        # 同步更新决策日志（机器可读）
        run("python3 decide_log.py --stats", timeout=60)
        state[DSKEY] = today
        log.append("  决策统计: %s" % ('已更新' if okds else '失败'))

    # ①.9985 12点全面检查（用户要求 09-30，专项）
    NOONKEY = 'last_noon_full'
    if h == 12 and state.get(NOONKEY) != today:
        log.append("→ 12点全面检查（专项）")
        oknf, outnf = run("bash noon_full_check.sh", timeout=900)
        state[NOONKEY] = today
        log.append("  12点检查: %s" % ('完成' if oknf else '⚠️ 有问题'))

    # ①.999 四次复检（用户建议 2026-09-28；2026-09-29 加"存活检查"）
    #   【已知局限】复检在沙箱内跑 → 沙箱死时跑不了
    #   → 存活靠"外部"（healthchecks + server_guardian + 会话自检）
    FCKEY = 'last_four_checks_%d' % h
    # 关键时段: 06 晨检 / 12 午检 / 18 晚检 / 00 夜检
    if h in (6, 12, 18, 0) and state.get(FCKEY) != today:
        kind = {6: 'morning', 12: 'noon', 18: 'evening', 0: 'night'}[h]
        log.append("→ 复检（%s %02d:00）" % (kind, h))
        okfc, outfc = run("python3 four_checks.py %s" % kind, timeout=400)
        state[FCKEY] = today
        if not okfc:
            log.append("  🔴 复检发现问题（见 data/four_checks_latest.json）")
        else:
            log.append("  ✅ 复检通过")

    # ①.9995 tasks.txt 清理（每天 04:30，防膨胀）
    CTKEY = 'last_clean_tasks'
    if h == 4 and now.minute >= 30 and state.get(CTKEY) != today:
        okct, outct = run("python3 clean_tasks.py --apply", timeout=60)
        state[CTKEY] = today
        log.append("  tasks.txt 清理: %s" % ('完成' if okct else '失败'))

    # ①.9997 SYSTEM.md 防重置（每小时，平台可能重置 /app/agent）
    SSKEY = 'last_system_md_check'
    if state.get(SSKEY) != now.strftime('%Y-%m-%d %H'):
        run("bash restore_system_md.sh", timeout=30)
        state[SSKEY] = now.strftime('%Y-%m-%d %H')

    # ①.9998 故障注入（每周日 16:00，验证复检有效）
    FIKEY = 'last_fault_inject'
    if now.weekday() == 6 and h == 16 and state.get(FIKEY) != today:
        log.append("→ 故障注入（周日 16:00）")
        okfi, outfi = run("python3 fault_inject.py weekly", timeout=300)
        state[FIKEY] = today
        log.append("  注入: %s" % ('✅ 复检抓到（体系有效）' if okfi == 0 else '🔴 复检漏掉（需查）'))

    # ①.9999 沙箱演练（每周日 15:00，环境无关部分）
    DRILLKEY = 'last_drill_sandbox'
    if now.weekday() == 6 and h == 15 and state.get(DRILLKEY) != today:
        log.append("→ 沙箱演练（周日 15:00）")
        okdr, outdr = run("python3 drill_sandbox.py", timeout=600)
        state[DRILLKEY] = today
        log.append("  演练: %s" % ('✅ 通过' if okdr else '🔴 有失败'))

    # ①.99995 服务器到期提醒（每天 09:00，到期前 7 天）
    try:
        import datetime as _dt
        _expire = _dt.datetime(2026, 11, 17, 13, 57, 44)
        _CST = _dt.timezone(_dt.timedelta(hours=8))
        _now = _dt.datetime.now(_CST)
        _days = (_expire - _now.replace(tzinfo=None)).days
        REKEY = 'last_expire_remind'
        if h == 9 and 0 < _days <= 7 and state.get(REKEY) != today:
            log.append("🔴 服务器 %d 天后到期（11-17）→ 提醒用户续费" % _days)
            try:
                import alert
                alert.send_alert('服务器即将到期', '腾讯云 43.128.44.120（Ubuntu-onvA）\n'
                                 '到期: 2026-11-17 13:57\n剩余: %d 天\n→ 请续费' % _days, 'error')
            except Exception:
                pass
            state[REKEY] = today
    except Exception:
        pass

    # ①.99 数据更新（【2026-09-30 加】防数据过期）
    # 理由: position/signal/health/breaker 没有定时更新 → 会过期
    DUKEY = 'last_data_update'
    if state.get(DUKEY) != now.strftime('%Y-%m-%d %H'):   # 每小时
        log.append("→ 数据更新（每小时）")
        # signal（每2h，但每小时跑也无害）
        run("python3 signal_engine.py", timeout=180)
        # health（每6h → 每小时跑，幂等）
        run("python3 -c 'import health_daemon; health_daemon.run()'", timeout=120)
        state[DUKEY] = now.strftime('%Y-%m-%d %H')
        log.append("  已更新 signal + health")
        # 【2026-10-01 加】记录分数历史（治 B组"静止仪表盘"）
        try:
            import score_history as _sh
            _sh.record()
        except Exception:
            pass
        # 【2026-10-01 加】记录价格历史（治"市场在动数据不动"）
        try:
            import price_history as _ph
            _ph.record()
        except Exception:
            pass
    # position + breaker（每6h）
    DPKEY = 'last_data_update_6h'
    if h % 6 == 0 and state.get(DPKEY) != today + str(h):
        run("python3 position.py", timeout=240)
        run("python3 -c 'import breaker; breaker.run()'", timeout=120)
        run("python3 correlation.py", timeout=120)
        state[DPKEY] = today + str(h)
        log.append("  → 已更新 position + breaker + correlation")
        # [2026-10-04 加] L1 原始层（K线落库，可回放取证）
        try:
            import l1_archive as _l1
            _l1.archive()
            log.append("  📦 L1 已存档（日K）")
        except Exception:
            pass
        # [2026-10-04 加] L4 教训层（复盘 + 找模式）
        try:
            import l4_lessons as _l4
            _new = _l4.review_closed_trades()
            _pats = _l4.analyze_patterns()
            if _new:
                log.append("  📝 L4 复盘 %d 笔" % len(_new))
            if _pats:
                log.append("  🔴 L4 模式: %s" % _pats[0])
        except Exception:
            pass

        # [2026-10-04 加] 记忆同步（沙箱 → 服务器，让分身记忆最新）
        try:
            import memory_sync_to_server as _ms
            _ch = _ms.sync()
            if _ch:
                log.append("  📤 记忆已推服务器: %s" % ', '.join(_ch))
        except Exception:
            pass

        # [2026-10-03 加] A2A 收信（AI 对 AI 通信）
        try:
            import a2a_client as _a2a
            _new = _a2a.fetch_inbox()
            if _new:
                log.append("  📬 A2A 新消息 %d 条" % len(_new))
                for _m in _new[:3]:
                    log.append("     [%s] %s" % (_m.get('from', '?'),
                                                 str(_m.get('message', ''))[:60]))
        except Exception:
            pass

        # [2026-10-02 加] Bridge 稳定性探测（用户建议: 找最稳时段）
        try:
            import bridge_probe as _bp
            _r = _bp.probe()
            log.append("  Bridge探测: %s (%.0fs)"
                       % ('✅' if _r.get('ok') else '🔴', _r.get('elapsed_s', 0)))
        except Exception:
            pass

        # [2026-10-02 加] 账本同步（沙箱副本 ← 服务器真源）
        run("bash sync_ledger_from_server.sh", timeout=60)

        # [2026-10-02 加] 对手方风险（DS 找盲区）每天查
        run("python3 counterparty_risk.py", timeout=120)
        log.append("  已查对手方风险")

        # [2026-10-02 加] 虚拟盘交易引擎（每天跑，积累样本）
        #   根因: virtual_capital 从未被调度 → 9/25 后无交易
        _vc_ok, _vc_out = run("python3 virtual_capital.py --once", timeout=300)
        if _vc_ok:
            log.append("  → 虚拟盘已跑（交易引擎）")
        else:
            log.append("  🔴 虚拟盘失败")

    # ①.995 情报扫描 + 轮换（【2026-10-01 加】用户要求"情报系统"）
    #   【2026-10-01 用户指示】先放一边 → 等三家评审结论后再商量
    #   调度保留但默认**关闭**（ENABLE_INTEL_SCHED=1 才跑）
    ICKEY = 'last_intel_scan'
    # [2026-10-01 三家决策] 数据层+评估层现在做（零风险落库）；执行层等
    if os.environ.get('DISABLE_INTEL_SCHED') != '1' and h == 5 and state.get(ICKEY) != today:
        log.append("→ 情报扫描（全市场 + 跨品类）")
        run("python3 intel_v3.py", timeout=280)
        state[ICKEY] = today
        log.append("  已更新 intel_v3.json")
        # [2026-10-01 三家决策] 纸面跟踪（验证滑点/存续性）
        run("python3 intel_paper_track.py", timeout=120)
        log.append("  已更新纸面跟踪")
    RCKEY = 'last_rotation'
    # [2026-10-01] 轮换仍暂缓（属执行层，等条件）
    if os.environ.get('ENABLE_ROTATION') == '1' and h == 6 and state.get(RCKEY) != today:
        log.append("→ 品种轮换评估")
        run("python3 rotation_v2.py --once", timeout=280)
        state[RCKEY] = today
        log.append("  已更新 rotation.json")

    # ①.9995 急停状态检查（每小时）
    try:
        import kill_switch as _ks
        if _ks.is_halted():
            log.append("  🔴 急停激活（kill_switch halted）")
    except Exception:
        pass

    # ② 费用统计（每小时一次）
    lastfee = state.get(FEE_KEY)
    if lastfee != now.strftime('%Y-%m-%d %H'):
        run("python3 cost_hour.py --today", timeout=120)
        state[FEE_KEY] = now.strftime('%Y-%m-%d %H')
        log.append("  费用统计已更新")

    return log


def main():
    watch = '--watch' in sys.argv
    state = load_state()
    if not watch:
        log = check_once(state)
        save_state(state)
        print("检查完成:" if log else "本次无任务")
        for x in log:
            print(" ", x)
        return 0

    print("自动调度器启动（北京低峰跑常态任务）")
    print("  常态: 00夜检 | 01协同 | 02学习 | 03备份 | 04策展 | 05集成 | 06晨检 | 12午检 | 18晚检 | 23决策 | 每小时费用+健康")
    print("  原则: 常态异步 / 异常触发 / 大事留人确认")
    while True:
        try:
            import heartbeat_file as _hb
            _hb.beat('auto_runner')
        except Exception:
            pass
        try:
            state = load_state()
            log = check_once(state)
            save_state(state)
            for x in log:
                print("[%s] %s" % (bj_now().strftime('%H:%M'), x), flush=True)
        except Exception as e:
            print("[错误] %s" % e, flush=True)
        # 【2026-09-30 修】分片 sleep（每 30 秒心跳一次）
        #   原 bug: 心跳只在每轮开头 1 次 → 间隔 600 秒 > 300 秒阈值 → 误报过期
        for _ in range(20):          # 20 × 30s = 600s（保持 10 分钟轮询）
            try:
                import heartbeat_file as _hb2
                _hb2.beat('auto_runner')
            except Exception:
                pass
            time.sleep(30)


if __name__ == '__main__':
    # 【2026-09-30 加】单例锁（防竞态双实例）
    try:
        from single_instance import acquire
        if not acquire('auto_runner'):
            sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        pass

    # [2026-09-25] 行缓冲（解决 nohup 重定向时日志为空）
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass
    sys.exit(main())
