# 可见层 · 二哥的体检证据（可复算）

## 文件
- monitor_alive.json（监控活性检测输出）
- score_history.json（分数历史，50条）

## 复算命令
```bash
# 复算"连续不变"
python3 -c "
import json
rows=json.load(open('score_history.json'))
same=1
for r in reversed(rows[:-1]):
    if r['scores']==rows[-1]['scores']: same+=1
    else: break
print('连续不变:', same)
"
```

## 结论（我跑的）
- 连续不变: 12 ✅
- 持仓-评分脱节: DOGE/XRP（不在持仓，有分）
