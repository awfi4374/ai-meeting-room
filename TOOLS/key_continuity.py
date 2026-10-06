#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
key 连续性方案 v2 (key_continuity.py)
=======================================
MasterD(区块链·大哥) · 2026-10-06

【今天发现的真问题（演练测出来的）】
  Bug① "真连测试"不带 -i → ssh 走默认查找 → "假绿"（已修）
  Bug② 恢复链"鸡生蛋"：key 丢了就没法连服务器拉 key

【解法（合并五兄弟意见）】
  老四：分层分级 → SSH key 是"可重建"资产
  三哥：指纹校验 + "真用一次" + ★"注入已知坏，看能不能测出"（可证伪）
  老五：密文多处 + 密码单处
  二哥：自动恢复 + 定期演练

【最终方案】
  ① 本机存"加密的 key"（AES-256-PBKDF2，密码单独记）→ 破"鸡生蛋"
  ② 恢复路径：服务器 vault（.bak）+ 本机密文 = 双路
  ③ 校验：指纹比对 + 真连测试（带 -i，不假绿）
  ④ 演练：--drill（真删→恢复→验证，可证伪）
"""
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

KEY_LOCAL = Path('/app/agent/state/sshkeys/masterd')
KEY_ENC = Path('/app/agent/state/sshkeys/masterd.enc')     # 本机加密副本
KEY_SERVER = '/opt/masterd/memory/keys/masterd_ssh_key_plain.bak'
PASS_FILE = Path('/app/agent/state/sshkeys/.keypass')       # 密码（600；★生产应存别处）
HOST = 'root@43.161.226.155'
SSH_OPTS = ['-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=8', '-o', 'IdentitiesOnly=yes']


def sh(cmd, timeout=25):
    try:
        return subprocess.check_output(cmd, shell=True, text=True,
                                       timeout=timeout).strip()
    except Exception as e:
        return f'__ERR__{e}'


def fingerprint(path):
    """SHA256 前 16 位（三哥的指纹法）"""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except Exception:
        return None


def get_pass():
    if PASS_FILE.exists():
        return PASS_FILE.read_text().strip()
    return None


def encrypt_backup():
    """① 加密备份（破'鸡生蛋'：本机密文，密码单独记）"""
    pw = get_pass()
    if not pw:
        pw = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
        PASS_FILE.write_text(pw)
        PASS_FILE.chmod(0o600)
    r = sh(f"openssl enc -aes-256-cbc -pbkdf2 -iter 100000 "
           f"-in {KEY_LOCAL} -out {KEY_ENC} -pass pass:{pw}")
    return {"ok": KEY_ENC.exists(), "path": str(KEY_ENC),
            "fp": fingerprint(KEY_ENC)}


def decrypt_restore():
    """② 从本机密文恢复（不需要连服务器！破'鸡生蛋'）"""
    pw = get_pass()
    if not pw:
        return {"ok": False, "reason": "无密码文件"}
    r = sh(f"openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 "
           f"-in {KEY_ENC} -pass pass:{pw}")
    if 'OPENSSH PRIVATE KEY' not in r:
        return {"ok": False, "reason": f"解密失败: {r[:60]}"}
    KEY_LOCAL.write_text(r if r.endswith('\n') else r + '\n')
    KEY_LOCAL.chmod(0o600)
    return {"ok": True, "reason": "已从本机密文恢复", "fp": fingerprint(KEY_LOCAL)}


def check_local():
    if not KEY_LOCAL.exists():
        return {"ok": False, "fp": None}
    return {"ok": True, "fp": fingerprint(KEY_LOCAL)}


def check_real_use():
    """真用一次（带 -i，不假绿）"""
    if not KEY_LOCAL.exists():
        return {"ok": False, "reason": "key 不存在"}
    out = sh(f"ssh -i {KEY_LOCAL} " + ' '.join(SSH_OPTS) + f" {HOST} echo KEYOK")
    return {"ok": 'KEYOK' in out, "reason": "真连成功" if 'KEYOK' in out else f"失败:{out[:50]}"}


def recover_from_server():
    """③ 从服务器拉（需 key 可用；不可用时走本机密文）"""
    prep = sh(f"ssh -i {KEY_LOCAL} " + ' '.join(SSH_OPTS) +
              f" {HOST} 'cp {KEY_SERVER} /root/_k.pem 2>/dev/null; "
              f"chmod 600 /root/_k.pem; echo done'")
    if 'done' not in prep:
        return {"ok": False, "reason": "服务器不可达（走本机密文）"}
    tmp = '/tmp/_k_recover'
    sh(f"scp " + ' '.join(SSH_OPTS) + f" -i {KEY_LOCAL} {HOST}:/root/_k.pem {tmp}")
    if not Path(tmp).exists():
        return {"ok": False, "reason": "拉取失败"}
    shutil.copy(tmp, KEY_LOCAL)
    KEY_LOCAL.chmod(0o600)
    sh(f"ssh -i {KEY_LOCAL} " + ' '.join(SSH_OPTS) + f" {HOST} 'rm -f /root/_k.pem'")
    return {"ok": True, "reason": "已从服务器恢复", "fp": fingerprint(KEY_LOCAL)}


def drill(real=False):
    """④ 演练（可证伪）"""
    print("=" * 58)
    print(f"key 连续性演练 {'（真删真恢复）' if real else '（常规检查）'}")
    print("=" * 58)
    print(f"时间：{datetime.now().isoformat()[:19]}\n")

    b = check_local()
    u = check_real_use()
    print(f"① 本地 key：{'✅' if b['ok'] else '❌'} 指纹={b['fp']}")
    print(f"② 真连测试：{'✅' if u['ok'] else '❌'} {u['reason']}")
    print(f"③ 本机密文：{'✅ 在' if KEY_ENC.exists() else '❌ 无'} 指纹={fingerprint(KEY_ENC)}")

    if real:
        print("\n★ 真演练：删除本地 key → 从密文恢复 → 验证")
        backup = KEY_LOCAL.read_bytes()
        KEY_LOCAL.unlink()
        print(f"   删除后：{'❌ 无 key' if not KEY_LOCAL.exists() else '仍在'}")
        r = decrypt_restore()
        print(f"   恢复：{'✅ ' + r['reason'] if r['ok'] else '❌ ' + r['reason']}")
        u2 = check_real_use()
        print(f"   恢复后真连：{'✅ ' + u2['reason'] if u2['ok'] else '❌ ' + u2['reason']}")
        if b['fp'] == check_local()['fp']:
            print(f"   指纹一致：✅ ({b['fp']}) —— 恢复无损")
        else:
            print(f"   ⚠️ 指纹不一致！（演练前{b['fp']} vs 后{check_local()['fp']}）")
    else:
        print("\n★ 结论：见上。跑 --drill-real 做真演练。")


def main():
    if '--encrypt' in sys.argv:
        print(encrypt_backup()); return
    if '--restore' in sys.argv:
        print(decrypt_restore()); return
    if '--check' in sys.argv:
        b = check_local(); u = check_real_use()
        print(f"本地key: {'✅' if b['ok'] else '❌'} 指纹={b['fp']}")
        print(f"真连测试: {'✅' if u['ok'] else '❌'} {u['reason']}")
        print(f"本机密文: {'✅' if KEY_ENC.exists() else '❌'}")
        return
    if '--recover' in sys.argv:
        r = recover_from_server()
        if not r['ok']:
            print("服务器路不通 →", decrypt_restore())
        else:
            print(r)
        return
    drill(real='--drill-real' in sys.argv)


if __name__ == '__main__':
    main()
