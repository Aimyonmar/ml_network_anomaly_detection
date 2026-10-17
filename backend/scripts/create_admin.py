"""管理员账号下发命令（V3，CONTEXT.md §11.3）。

定位：管理员账号的唯一来源。注册接口永远只能创建普通用户（role=user），
管理员仅能由机器主人在部署服务器本地执行本命令下发。

用法（项目根目录，venv 已激活）：
    python backend/scripts/create_admin.py <username>

行为：
- 生成 16 位随机强密码（大小写字母+数字，约 95 bit 熵），仅在创建时显示一次
- 用户名已存在（无论 role）一律拒绝：不做静默提权、不覆盖已有账号
  （如需提权/重置密码，下期单独做，避免本命令成为误操作入口）

提示：Windows 下抓包相关功能（一键体检）与权限相关，管理员密码请立即妥善保存。
"""
import os
import secrets
import string
import sys
from pathlib import Path

# 让脚本无论从项目根还是 backend/ 目录启动都能 import app.*；
# 并切 cwd 到 backend/，保证 config 的 env_file=".env" 等相对路径与 uvicorn 部署口径一致
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

PASSWORD_ALPHABET = string.ascii_letters + string.digits
PASSWORD_LENGTH = 16


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python backend/scripts/create_admin.py <username>")
        return 1
    username = sys.argv[1].strip()
    if not username:
        print("[错误] 用户名不能为空")
        return 1

    from app.database import SessionLocal
    from app.models import User
    from app.security import hash_password

    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == username).first()
        if exists is not None:
            print(f"[拒绝] 用户名 {username!r} 已存在"
                  f"（当前 role={exists.role}）。本命令不覆盖已有账号、不做提权；"
                  "如下发新管理员请换一个用户名。")
            return 1

        password = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))
        db.add(User(username=username, password=hash_password(password), role="admin"))
        db.commit()
    finally:
        db.close()

    print(f"[下发成功] 管理员账号已创建：{username}")
    print(f"初始密码（仅此一次显示，请立即保存）：{password}")
    print("请用该账号通过正常登录入口登录；密码入库为 bcrypt 哈希，无法找回，丢失需重新下发新账号。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
