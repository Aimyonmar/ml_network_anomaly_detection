"""一键体检抓包服务（V3，CONTEXT.md §11.2）。

职责：
- 在部署机本机按定长窗口抓包（30/60/120 秒，由路由层校验）
- 抓到的包写入任务预分配的临时 pcap 路径
- 复用 detection.run_detection 全链路（流特征提取→v2 模型→写库→告警），
  检测/失败状态机完全沿用现有实现，本文件不重复造状态机

诚实边界（CONTEXT.md §11.2，产品页同步展示）：
- 抓的是部署机网卡流量：本机部署=检测本机；远程部署只能检测服务器自身
- 体检窗口内无流量时由 flow_extract 的既有报错兜底（task failed + error_msg）

注意：本函数由 BackgroundTasks 调用，运行在请求响应之后，
必须自己管理 DB session（不能复用请求作用域的 get_db）。
"""
from pathlib import Path

from loguru import logger

from app.models import DetectionTask
from app.services.detection import run_detection


def run_live_detection(task_id: int, duration: int) -> None:
    """一键体检后台任务入口：抓包 → 落 pcap → 复用 run_detection。

    任何抓包异常都落 failed + error_msg；检测阶段的状态机/失败清理
    （含临时 pcap 删除）由 run_detection 全权处理。
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        task = db.get(DetectionTask, task_id)
        if task is None:
            logger.error(f"[live] task_id={task_id} 不存在，放弃")
            return
        task.status = "running"  # 抓包阶段即视为进行中，前端轮询可见
        db.commit()
        pcap_path = Path(task.file_path)
    finally:
        db.close()

    try:
        # scapy 延迟导入：未装 scapy 的环境（v1 链路）不受影响
        from scapy.all import conf, sniff, wrpcap

        iface = conf.iface  # 系统默认路由网卡；高级用法（指定网卡）走 CLI，不在网页暴露
        logger.info(f"[live] task={task_id} 开始抓包 iface={iface} duration={duration}s")
        pkts = sniff(iface=iface, store=True, timeout=duration)
        wrpcap(str(pcap_path), pkts)
        logger.info(f"[live] task={task_id} 抓包完成 {len(pkts)} 包 → {pcap_path}")
    except Exception as exc:
        db = SessionLocal()
        try:
            task = db.get(DetectionTask, task_id)
            if task is not None:
                task.status = "failed"
                task.error_msg = f"抓包失败：{exc}"[:512]
                db.commit()
            logger.exception(f"[live] task={task_id} 抓包失败：{exc}")
        finally:
            db.close()
        return

    # 复用现有检测链路：pcap → 流特征 → 模型 → 结果/告警/状态机/失败清理
    run_detection(task_id, str(pcap_path))
