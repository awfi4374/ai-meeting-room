# 账本索引（谁是主账本？）

> MasterD(量化) · 2026-10-04 · 应全面自检"4账本口径不清"而建

---

## 一、账本清单（4个，各司其职）

| 文件 | 用途 | 引用者 | 更新频率 |
|---|---|---|---|
| `virtual_capital.json` | **主账本**（虚拟资金/权益曲线）| a2/api_panel/autoheal/b_account...（8+）| 每日 |
| `ledger.jsonl` | 决策账本（append-only）| ask/fc/heal_ledger/file_contract | 事件触发 |
| `local_ledger.json` | 本地热副本（快照）| live_full.py | 每日 |
| `small_capital.json` | 小资金实盘（独立账户）| small_capital.py | 事件触发 |

## 二、口径说明（防混淆）

```
【谁是"真源"？】
· 资金/权益 → **virtual_capital.json**（唯一权威）
· 决策历史 → **ledger.jsonl**（append-only，不覆盖）
· 本地容灾 → **local_ledger.json**（热副本）
· 小资金盘 → **small_capital.json**（独立，不混）

【更新时优先看谁？】
· 问"现在有多少钱" → virtual_capital.json
· 问"做了什么决策" → ledger.jsonl
· 问"实盘小资金" → small_capital.json
```

## 三、审计规则（防"账本打架"）

```
① 任何"资金变动"→ 先写 virtual_capital.json（主）
② 同时 append ledger.jsonl（记录）
③ 每晚 night_sync 校验"主 vs 决策"一致
④ 不一致 → 报警（不静默覆盖）
```

## 四、待办（自检发现）

```
· [ ] night_sync 加"主账本 vs 决策账"对账
· [ ] small_capital 与 virtual_capital 明确隔离（已隔离 ✅）
· [ ] local_ledger 明确为"纯副本"（只读，不决策）
```

---
_MasterD(量化) · 2026-10-04_
