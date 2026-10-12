"""【非项目范围·写来玩的】scapy 真抓包实时检测原型。

抓本机网卡流量 → 按目标 IP 聚合连接特征 → 降级映射到 NSL-KDD 41 列 → 模型判定。

重要局限（玩票口径，见 DECISIONS.md 2026-10-12 条）：
- 真实流量无法还原 NSL-KDD 的聚合统计特征（count/srv_rate 等训练时由
  专用工具预计算），只能做降级映射，判定结果参考意义有限，
  大概率把正常流量误判成 Attack——这是特征分布漂移，不是模型坏了。
- 仅抓自己这台机器的流量，不针对任何未授权网络。

依赖（不进项目白名单，playground 独立管理）：
    pip install scapy

用法（venv 已激活，在项目根目录）：
    python playground/live_capture.py --list              # 列出可用网卡
    python playground/live_capture.py                     # 自动选默认网卡，跑 60 秒
    python playground/live_capture.py --duration 120      # 跑 120 秒
    python playground/live_capture.py --iface 5           # 按网卡名或 --list 序号指定
"""
import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from ml import predict as ml_predict  # noqa: E402
from scapy.all import IP, TCP, UDP  # noqa: E402

# 41 列里能映射的数值列的默认填充值（抓不到就按"静默连接"填）
NUM_DEFAULTS = {
    "duration": 0, "src_bytes": 0, "dst_bytes": 0, "wrong_fragment": 0,
    "urgent": 0, "hot": 0, "num_failed_logins": 0, "num_compromised": 0,
    "root_shell": 0, "su_attempted": 0, "num_root": 0, "num_file_creations": 0,
    "num_shells": 0, "num_access_files": 0, "num_outbound_cmds": 0,
    "count": 1, "srv_count": 1, "serror_rate": 0.0, "srv_serror_rate": 0.0,
    "rerror_rate": 0.0, "srv_rerror_rate": 0.0, "same_srv_rate": 1.0,
    "diff_srv_rate": 0.0, "srv_diff_host_rate": 0.0, "dst_host_count": 1,
    "dst_host_srv_count": 1, "dst_host_same_srv_rate": 1.0,
    "dst_host_diff_srv_rate": 0.0, "dst_host_same_src_port_rate": 1.0,
    "dst_host_srv_diff_host_rate": 0.0, "dst_host_serror_rate": 0.0,
    "dst_host_srv_serror_rate": 0.0, "dst_host_rerror_rate": 0.0,
    "dst_host_srv_rerror_rate": 0.0,
}
BOOL_DEFAULTS = {
    "land": False, "logged_in": False, "is_host_login": False, "is_guest_login": False,
}
FEATURE_NAMES = ml_predict.load_expected_features()

# 常见服务端口 → NSL-KDD service 名映射（能对上多少算多少）
PORT_TO_SERVICE = {
    20: "ftp_data", 21: "ftp", 22: "ssh", 23: "telnet", 25: "SMTP",
    53: "domain_u", 80: "HTTP", 110: "POP3", 119: "nntp", 143: "IMAP4",
    443: "HTTPS", 465: "SMTP", 993: "IMAP4", 995: "POP3", 3306: "SQLNet",
    3389: "X11", 5432: "postgres", 6379: "other", 8080: "HTTP",
}
TCP_FLAGS = ["SF", "S0", "REJ", "RSTO", "RSTOS0", "SH", "OTHER"]


def build_record(dst_ip: str, flow: dict) -> dict:
    """把一个目的 IP 的聚合流量映射成模型输入记录（降级映射）。"""
    rec = {}
    ports = flow["ports"]
    main_port = max(ports, key=ports.get) if ports else 0
    for name in FEATURE_NAMES:
        if name == "protocol_type":
            rec[name] = "tcp" if flow["tcp"] >= flow["udp"] else ("udp" if flow["udp"] else "icmp")
        elif name == "service":
            rec[name] = PORT_TO_SERVICE.get(main_port, "other")
        elif name == "flag":
            rec[name] = "S0" if flow["syn_only"] > flow["established"] else "SF"
        elif name in ("land", "logged_in", "is_host_login", "is_guest_login"):
            rec[name] = BOOL_DEFAULTS[name]
        elif name == "duration":
            rec[name] = max(0, int(time.time() - flow["first_seen"]))
        elif name == "src_bytes":
            rec[name] = flow["bytes_out"]
        elif name == "dst_bytes":
            rec[name] = flow["bytes_in"]
        elif name == "count":
            rec[name] = flow["pkts"]
        elif name == "srv_count":
            rec[name] = ports.get(main_port, 1)
        else:
            rec[name] = NUM_DEFAULTS.get(name, 0)
    return rec


def packet_handler(state: dict, pkt):
    """scapy 回调：按目的 IP 聚合包特征。"""
    if IP not in pkt:
        return
    ip = pkt[IP]
    now = time.time()
    flow = state["flows"].setdefault(
        ip.dst,
        {"first_seen": now, "pkts": 0, "bytes_in": 0, "bytes_out": 0,
         "tcp": 0, "udp": 0, "syn_only": 0, "established": 0, "ports": defaultdict(int)},
    )
    flow["pkts"] += 1
    payload_len = len(pkt.getlayer(IP).payload) if IP in pkt else 0
    flow["bytes_out"] += payload_len  # 本机发出的量粗略记在 out
    if TCP in pkt:
        flow["tcp"] += 1
        tcp = pkt[TCP]
        flow["ports"][int(tcp.dport)] += 1
        flags = str(tcp.flags)
        if flags == "S":
            flow["syn_only"] += 1
        elif "A" in flags:
            flow["established"] += 1
    elif UDP in pkt:
        flow["udp"] += 1
        flow["ports"][int(pkt[UDP].dport)] += 1
    state["total_pkts"] += 1


def run(args) -> int:
    try:
        import scapy.all
    except ImportError:
        print("[错误] 未安装 scapy。先执行：pip install scapy")
        return 1

    if args.list:
        from scapy.all import IFACES
        print("可用网卡（--iface 用 NAME 列）：")
        print(f"  {'IDX':<4} {'NAME':<28} DESCRIPTION")
        for idx, iface in enumerate(IFACES.values()):
            print(f"  {idx:<4} {iface.name:<28} {iface.description}")
        return 0

    # 选网卡：--iface 支持网卡名或 --list 里的序号；缺省用系统默认路由网卡
    from scapy.all import IFACES, conf
    candidates = list(IFACES.values())
    if args.iface is not None:
        if args.iface.isdigit() and int(args.iface) < len(candidates):
            iface_obj = candidates[int(args.iface)]
        else:
            iface_obj = next((i for i in candidates if i.name == args.iface), None)
        if iface_obj is None:
            print(f"[错误] 找不到网卡：{args.iface}（用 --list 查看可用网卡）")
            return 1
    else:
        iface_obj = conf.iface
        if iface_obj is None:
            print("[错误] 找不到默认网卡，请用 --list 查看后 --iface 指定")
            return 1
    iface = iface_obj.name

    print(f"[抓包] 网卡={iface} 时长={args.duration}s 间隔={args.interval}s 判定/批")
    print("[警告] 真实流量→NSL-KDD 特征是降级映射，误报属预期，判定仅供体验，不作安全依据。\n")

    model = ml_predict.load_model()
    state = {"flows": {}, "total_pkts": 0}
    t_end = time.time() + args.duration
    n_judged = 0

    from scapy.all import sniff

    def sniff_worker():
        sniff(iface=iface_obj, prn=lambda p: packet_handler(state, p), store=False, timeout=args.duration)

    import threading
    th = threading.Thread(target=sniff_worker, daemon=True)
    th.start()

    try:
        while time.time() < t_end and th.is_alive():
            time.sleep(args.interval)
            if not state["flows"]:
                print(f"[{time.strftime('%H:%M:%S')}] 暂无流量 ...")
                continue
            # 每轮对当前活跃目的 IP 各判定一次
            snapshot = dict(state["flows"])
            print(f"\n[{time.strftime('%H:%M:%S')}] 已抓 {state['total_pkts']} 包，"
                  f"活跃目的 IP {len(snapshot)} 个：")
            for dst_ip, flow in sorted(snapshot.items(), key=lambda kv: -kv[1]["pkts"])[:10]:
                rec = build_record(dst_ip, flow)
                r = ml_predict.predict([rec], model)[0]
                n_judged += 1
                line = (f"  {dst_ip:<16} pkts={flow['pkts']:<6} "
                        f"svc={rec['service']:<7} flag={rec['flag']:<4} → {r['prediction']} "
                        f"(conf={r['confidence']:.3f})")
                print(f"\033[91m{line}\033[0m" if r["prediction"] == "Attack" else line)
    except KeyboardInterrupt:
        print("\n[中断] 手动停止")
    th.join(timeout=2)
    print(f"\n[结束] 共抓 {state['total_pkts']} 包，判定 {n_judged} 次。")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="scapy 真抓包实时检测（玩票原型）")
    parser.add_argument("--iface", default=None, help="网卡名（--list 查看）")
    parser.add_argument("--duration", type=int, default=60, help="抓包时长（秒），默认 60")
    parser.add_argument("--interval", type=int, default=5, help="判定间隔（秒），默认 5")
    parser.add_argument("--list", action="store_true", help="列出可用网卡")
    sys.exit(run(parser.parse_args()))
