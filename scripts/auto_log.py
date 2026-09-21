# scripts/auto_log.py
# 用法：python scripts/auto_log.py [changelog|images|check|all]
import subprocess, re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.now().strftime("%Y-%m-%d")


def git_changed_files():
    """今天 git 里改动过的文件列表"""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True
        ).strip()
        return [p for p in out.splitlines() if p and not p.startswith("screenshots/")]
    except Exception:
        return []


def git_recent_commits(n=5):
    try:
        return subprocess.check_output(
            ["git", "log", "--oneline", f"-{n}"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return ""


def ensure_table(path, headers):
    """如果文件不存在或为空，写入表头"""
    if not path.exists() or path.read_text(encoding="utf-8").strip() == "":
        row = "| " + " | ".join(headers) + " |\n"
        sep = "|---" * len(headers) + "|\n"
        path.write_text(row + sep, encoding="utf-8")
        print(f"[init] 创建 {path.name}，表头: {headers}")


def cmd_changelog():
    files = git_changed_files()
    commits = git_recent_commits()
    path = ROOT / "CHANGELOG.md"
    ensure_table(path, ["日期", "会话主题", "改动文件", "一句话说明", "遗留问题", "明日待办"])
    print(f"\n=== 今日 git 变动（请人工补充说明后交给记录员写入）===\n")
    print(f"日期: {TODAY}")
    print(f"改动文件({len(files)}):")
    for f in files[:15]:
        print(f"  - {f}")
    if len(files) > 15:
        print(f"  ... 还有 {len(files) - 15} 个")
    print(f"\n最近提交:\n{commits}")
    print("\n→ 把这些粘给记录员，配合 /log 使用。脚本不自动写内容，防止编造。")


def cmd_images():
    """扫描 screenshots/，同步 images-list.md"""
    d = ROOT / "screenshots"
    d.mkdir(exist_ok=True)
    rows = {}
    for f in sorted(d.glob("*.png")):
        m = re.match(r"(图\d+-\d+)_(.+)\.png", f.name)
        num = m.group(1) if m else "待编号"
        title = m.group(2) if m else f.name
        rows[num] = (f.name, title)
    lines = ["| 图号 | 文件名 | 标题 | 正文引用句 | 拍摄日期 |", "|---|---|---|---|---|"]
    for num in sorted(rows.keys()):
        fn, title = rows[num]
        lines.append(f"| {num} | {fn} | {title} | 如图{num[1:]}所示，… | {TODAY} |")
    (ROOT / "docs/images-list.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[images] 已同步 {len(rows)} 张截图 → docs/images-list.md")


def cmd_check():
    """一致性校验：抓 AI 编数字、设计与实现不一致"""
    errs = []
    # 1) METRICS.md 的 FINAL 是否与摘要/结论里的数字一致（扫全文）
    final = {}
    mp = ROOT / "METRICS.md"
    if mp.exists():
        text = mp.read_text(encoding="utf-8")
        m = re.search(r"## FINAL\s*\n(.+)", text)
        if m:
            for k, v in re.findall(r"(\w+)\s*=\s*([^\s,]+)", m.group(1)):
                final[k] = v
        for k, v in final.items():
            hits = len(re.findall(re.escape(v), text))
            if hits < 2:
                errs.append(f"FINAL 中 {k}={v} 在全文只出现 1 次，摘要/结论可能漏更新")
    else:
        errs.append("METRICS.md 不存在")

    # 2) schema.sql vs models.py 字段数粗略对齐
    sql = ROOT / "docs/schema.sql"
    mod = ROOT / "backend/app/models.py"
    if sql.exists() and mod.exists():
        tables = re.findall(r"CREATE TABLE (\w+)", sql.read_text(encoding="utf-8"))
        classes = re.findall(r"class (\w+)\(", mod.read_text(encoding="utf-8"))
        if len(tables) != len(classes):
            errs.append(f"schema.sql 有 {len(tables)} 张表，models.py 有 {len(classes)} 个模型类，数量不一致")

    # 3) DECISIONS.md 缺列检查
    dp = ROOT / "DECISIONS.md"
    if dp.exists():
        content = dp.read_text(encoding="utf-8")
        for tag in ["放弃的选项", "代价"]:
            if tag not in content:
                errs.append(f"DECISIONS.md 缺少列「{tag}」，请补表头并回填")

    # 4) 截图 orphan 检查
    imglist = ROOT / "docs/images-list.md"
    imgs = set(f.name for f in (ROOT / "screenshots").glob("*.png"))
    listed = set()
    if imglist.exists():
        listed = set(re.findall(r"\| [\w-]+ \| ([\w._-]+\.png) \|", imglist.read_text(encoding="utf-8")))
    for x in imgs - listed:
        errs.append(f"screenshots/{x} 未登记在 images-list.md")
    for x in listed - imgs:
        errs.append(f"images-list.md 登记了 {x}，但文件不存在")

    if not errs:
        print("[check] ✅ 全部通过")
    else:
        print("[check] ⚠️ 发现以下问题，修完再提交设计文档：")
        for i, e in enumerate(errs, 1):
            print(f"  {i}. {e}")


def cmd_all():
    cmd_changelog()
    cmd_images()
    cmd_check()


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    {"changelog": cmd_changelog, "images": cmd_images, "check": cmd_check, "all": cmd_all}.get(arg, cmd_all)()
