"""告警与处置建议服务（V2 产品化，Gap 4）。

链路：detection 检测完成 → 收集高置信 Attack 行 → 本服务去重落 t_alert
→ 生成处置建议命令（绝不自动执行）→ webhook 外发（失败只记日志不阻断）。

决策依据（DECISIONS.md 2026-10-12）：
- 处置力度 = 告警 + 建议：src_key 为 IPv4 时生成 Windows 防火墙封禁命令，
  由人工确认后自行复制执行；非 IP 源给人工复核文案。
- 自动阻断永久禁止（CONTEXT.md §10.2）。
"""
from __future__ import annotations

import ipaddress
import json
import urllib.request
from urllib.error import URLError

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Alert

# 单任务告警上限：超出的低置信源不告警（防爆表；如实写进产品页与 METRICS）
MAX_ALERTS_PER_TASK = 500


def _is_ipv4(s: str) -> bool:
    try:
        ipaddress.IPv4Address(s)
        return True
    except ValueError:
        return False


def build_rule_cmd(src_key: str) -> str | None:
    """处置建议命令生成（只生成文本，绝不执行）。

    IPv4 源 → Windows 防火墙入站封禁（人工复制到管理员 PowerShell 执行）；
    其他 → 人工复核文案。私网地址额外提示"先确认非内网正常业务"。
    """
    if not _is_ipv4(src_key):
        return f"人工复核：非 IP 攻击源（{src_key}），请在报告页定位原始记录"
    try:
        is_private = ipaddress.IPv4Address(src_key).is_private
    except ValueError:
        is_private = False
    cmd = (
        f'New-NetFirewallRule -DisplayName "NADS block {src_key}" '
        f"-Direction Inbound -RemoteAddress {src_key} -Action Block"
    )
    if is_private:
        cmd += "   # 注意：私网地址，执行前先确认不是内网正常业务"
    return cmd[:512]


def generate_alerts(
    db: Session,
    task_id: int,
    user_id: int,
    hits: list[dict],
) -> int:
    """把高置信攻击命中落成告警。

    hits: [{"row_no": int, "confidence": float, "src_key": str}, ...]
    去重：同 task 同 src_key 只保留置信度最高一条。
    限量：MAX_ALERTS_PER_TASK 内按置信度降序取。
    返回实际生成条数。
    """
    if not hits:
        return 0

    best: dict[str, dict] = {}
    for h in hits:
        key = h["src_key"] or f"row-{h['row_no']}"
        cur = best.get(key)
        if cur is None or h["confidence"] > cur["confidence"]:
            best[key] = {"row_no": h["row_no"], "confidence": h["confidence"], "src_key": key}

    ordered = sorted(best.values(), key=lambda x: -x["confidence"])[:MAX_ALERTS_PER_TASK]
    for h in ordered:
        db.add(Alert(
            task_id=task_id,
            user_id=user_id,
            src_key=h["src_key"][:64],
            confidence=h["confidence"],
            prediction="Attack",
            rule_cmd=build_rule_cmd(h["src_key"]),
            status="open",
        ))
    db.commit()
    logger.info(f"[alert] task={task_id} 生成告警 {len(ordered)} 条（去重前 {len(hits)} 命中）")
    send_webhook(task_id, user_id, ordered)
    return len(ordered)


def send_webhook(task_id: int, user_id: int, alerts: list[dict]) -> bool:
    """任务级摘要 webhook（一次一条，不逐告警轰炸）。

    - ALERT_WEBHOOK_URL 为空 → 不外发（返回 False，不算失败）
    - generic：{"text": "..."}；feishu：{"msg_type":"text","content":{"text":"..."}}（群机器人格式）
    - 发送失败（网络/5xx）只记 warning，绝不影响检测链路
    """
    url = settings.ALERT_WEBHOOK_URL
    if not url:
        return False

    top = ", ".join(f"{a['src_key']}({a['confidence']:.2f})" for a in alerts[:5])
    text = (
        f"[NADS 告警] 任务 #{task_id}（用户 {user_id}）产出 {len(alerts)} 条高置信攻击告警。"
        f"Top 源：{top or '无'}。请登录系统在告警页处置。"
    )
    if settings.ALERT_WEBHOOK_TYPE == "feishu":
        payload = {"msg_type": "text", "content": {"text": text}}
    else:
        payload = {"text": text}

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
        if 200 <= status < 300:
            logger.info(f"[alert] webhook 已发送 task={task_id} status={status}")
            return True
        logger.warning(f"[alert] webhook 响应非 2xx：{status}（不阻断检测）")
        return False
    except (URLError, OSError, ValueError) as exc:
        logger.warning(f"[alert] webhook 发送失败（不阻断检测）：{exc}")
        return False
