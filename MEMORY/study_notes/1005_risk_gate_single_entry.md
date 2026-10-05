# 学习笔记 · risk_gate_single_entry

> 维度: 自动扩充 | 时间: 2026-10-05 07:45:05
> 动机: 主题库扩展（10-05）

---

## 问题

如何设计一个"单一风控入口"（risk_gateway），使得任何新模块若未经它注册就无法进入生产链——并用调用图断言（call-graph assertion）在 CI 中自动拦截"绕过"？

---

## DeepSeek

**DeepSeek 回答：**

**1. 单一入口 = 装饰器 + 注册表（Python 示例）**
```python
REGISTRY = set()

def risk_gateway(fn):
    REGISTRY.add(fn.__qualname__)
    @wraps(fn)
    def wrapper(*a, **k):
        assert fn.__qualname__ in REGISTRY
        return health_gate(fn, *a, **k)   # 唯一风控闸口
    return wrapper
```
生产链上**只允许**调用被 `@risk_gateway` 装饰的函数；下单/调仓 API 全部包一层。

**2. 调用图断言（CI 拦截"绕过"）**
用 `pydeps` / `networkx` 静态建图：
```python
G = build_call_graph("src/")
forbidden = {"broker.place_order", "portfolio.rebalance"}
for f in forbidden:
    for p in nx.all_simple_paths(G, "main", f):
        assert any(n in REGISTRY for n in p), f"绕过风控: {p}"
```
**关键**：断言"从 main 到敏感函数的每条路径，必经注册节点"。任何新模块直连 broker → CI 红。

**3. 自曝弱点（先防被攻）**
- 动态调用（`getattr`/反射/插件加载）静态图**抓不到** → 需运行时兜底：敏感函数内部再查 `REGISTRY`（双保险）。
- 装饰器可被 `functools.wraps` 伪造 → 校验用**签名指纹**而非名字。
- 图覆盖不全（跨进程/子进程）→ 加 `sys.settrace` 采样，CI 跑一遍 paper_trade 收集真实调用边，与静态图 diff。

**4. 落地顺序**
① 先给 broker/portfolio 加断言（低风险）→ ② 补运行时校验 → ③ CI 加 diff 门禁。
**契约式验证 > 信任式交付。**

（约 340 字）

（3.0s / 1228 tokens）

---

## Kimi 补充

[高峰时段，跳过 Kimi]

---

## 可执行清单

# DeepSeek · 检查清单（可勾选）

> 从上面回答提炼 · 用于"单一入口 + 调用图断言"落地

---

## 落地检查清单（7 条）

- [ ] **1. 定义唯一闸口**：`health_gate` 作为风控唯一入口，所有下单/调仓必须经过它
- [ ] **2. 装饰器注册**：敏感函数（broker.place_order / portfolio.rebalance）全部加 `@risk_gateway`，注册进 `REGISTRY`
- [ ] **3. 运行时兜底**：敏感函数**内部**再查一次 `REGISTRY`（防动态调用绕过静态图）
- [ ] **4. 静态调用图断言**：用 `pydeps`/`networkx` 建图，断言"main → 敏感函数的每条路径必经注册节点"
- [ ] **5. CI 门禁**：新模块直连 broker → CI 直接红（阻断合并）
- [ ] **6. 动态边 diff**：`sys.settrace` 采样 paper_trade 真实调用边，与静态图 diff（抓跨进程/子进程）
- [ ] **7. 签名指纹校验**：用**函数签名指纹**而非名字校验（防 `functools.wraps` 伪造）

---

## ⚠️ 自曝弱点（先防被攻）

```
① 静态图抓不到动态调用（getattr/反射/插件）→ 靠第 3 条运行时兜底
② 装饰器可被伪造 → 靠第 7 条签名指纹
③ 跨进程/子进程图覆盖不全 → 靠第 6 条 settrace diff
④ 落地顺序: 先加断言(低风险) → 再补运行时 → 最后 CI 门禁
```

**核心一句：契约式验证 > 信任式交付。**

---

## 补充说明（诚实标注）

- 上面是**我（DeepSeek）**基于自己上一轮回答的提炼，**不是 Kimi 的独立验证**
- 本轮**未走 Kimi 信道**（高峰跳过）→ 存在**回音壁风险**
- 建议：下次 Kimi 在线时，让它**独立**回答同一问题（别看我的），再 diff 分歧

**分歧优先：如果 Kimi 给出不同落地顺序或不同弱点，以分歧为准深挖。**

（2.9s / 7565 tokens）
