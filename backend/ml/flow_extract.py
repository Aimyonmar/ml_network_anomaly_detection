"""pcap 流特征提取器（V2 产品化，Gap 1：多格式输入）。

职责：pcap → 双向流重组 → 产出 CIC-IDS2017 命名的流特征记录（降级子集），
供 v2 模型（cicids2017 schema）推理。

复用 playground/live_capture.py 已实测的 scapy 抓包可行性（本机原生后端，免 Npcap），
本模块只做离线文件读取（rdpcap），比 live_capture 的实时路径更简单。

诚实声明（产品页同步展示）：
- 只能计算 CICFlowMeter 78 特征中约 45 个（Subflow/Bulk/Active/Idle 等派生统计无法
  离线复刻），缺失列由 schema_registry.get_flow_schema().fill_defaults() 填 0；
- 训练（CIC 官方 CSV）与推理（本提取器）存在特征口径差异，pcap 检测结果仅供参考。

侧带字段：每条记录附 "_src_ip"/"_dst_ip"（正向流两端），供告警定位攻击源；
以 "_" 开头的键由 detection 剥离，不进模型。
"""
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

# TCP flag 位掩码（scapy flags 属性可直接按位与）
_FLAG_BITS = {
    "FIN": 0x01, "SYN": 0x02, "RST": 0x04, "PSH": 0x08,
    "ACK": 0x10, "URG": 0x20, "ECE": 0x40, "CWE": 0x80,
}


class FlowExtractError(ValueError):
    """pcap 解析/流重组失败时抛出，由 detection 转 task failed。"""


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    """总体标准差（与 statistics.pstdev 等价，手写以避免 stdlib pycache 写入问题）。"""
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def pcap_to_records(pcap_path: Path | str) -> list[dict]:
    """解析 pcap 文件，按双向五元组重组流，输出特征记录列表。"""
    from scapy.all import IP, TCP, UDP, rdpcap  # 延迟导入：无 pcap 链路不依赖 scapy

    packets = rdpcap(str(pcap_path))
    flows: dict[tuple, list] = defaultdict(list)
    first_seen: dict[tuple, int] = {}

    for idx, pkt in enumerate(packets):
        if IP not in pkt:
            continue  # 非 IPv4（ARP/广播等）不进流
        ip = pkt[IP]
        if TCP in pkt:
            proto, sport, dport = "tcp", int(pkt[TCP].sport), int(pkt[TCP].dport)
        elif UDP in pkt:
            proto, sport, dport = "udp", int(pkt[UDP].sport), int(pkt[UDP].dport)
        else:
            proto, sport, dport = "other", 0, 0
        a, b = (ip.src, sport), (ip.dst, dport)
        key = (proto,) + tuple(sorted([a, b]))
        flows[key].append((idx, float(pkt.time), len(pkt), ip))
        if key not in first_seen:
            first_seen[key] = idx

    if not flows:
        raise FlowExtractError(
            f"pcap 中没有可解析的 IPv4 数据包（共 {len(packets)} 包），无法提取流特征。"
        )

    records: list[dict] = []
    for key, pkts in flows.items():
        records.append(_flow_features(key, pkts))
    # 按首包出现顺序输出，保证 row_no 与包序对应，便于人工回查
    records.sort(key=lambda r: r["_first_idx"])
    for r in records:
        r.pop("_first_idx")
    return records


def _flow_features(key: tuple, pkts: list) -> dict:
    """单条双向流的特征计算（列名 = CIC-IDS2017 strip 后命名）。"""
    proto = key[0]
    # first_seen 顺序键（排序后剥离）
    pkts_sorted = sorted(pkts, key=lambda p: p[0])
    first_idx = pkts_sorted[0][0]
    first_pkt = pkts_sorted[0][3]  # IP 层

    # 正向 = 首包的 src→dst（CICFlowMeter 同口径）；key[1]/key[2] 为排序后的两端点
    if (first_pkt.src, _port_of(pkts_sorted[0])) == key[1]:
        fwd_ep, bwd_ep = key[1], key[2]
    else:
        fwd_ep, bwd_ep = key[2], key[1]

    fwd, bwd = [], []
    for idx, ts, length, ip in pkts_sorted:
        item = (idx, ts, length, ip)  # 与 pkts_sorted 同序：idx, ts, len, ip
        if ip.src == fwd_ep[0]:
            fwd.append(item)
        else:
            bwd.append(item)

    def lens(items):
        return [it[2] for it in items]

    def iats(items):  # μs
        tss = [it[1] for it in items]
        return [(b - a) * 1e6 for a, b in zip(tss, tss[1:])]

    def header_len(ip):
        return int(ip.ihl) * 4 + _l4_header_len(ip)

    t_all = [it[1] for it in pkts_sorted]
    l_all = [it[2] for it in pkts_sorted]
    duration_us = (t_all[-1] - t_all[0]) * 1e6 if len(t_all) > 1 else 0.0
    n_fwd, n_bwd = len(fwd), len(bwd)
    total_bytes = sum(l_all)
    total_pkts = len(pkts_sorted)

    rec: dict = {
        "Destination Port": bwd_ep[1] if isinstance(bwd_ep[1], int) else 0,
        "Flow Duration": duration_us,
        "Total Fwd Packets": n_fwd,
        "Total Backward Packets": n_bwd,
        "Total Length of Fwd Packets": sum(lens(fwd)),
        "Total Length of Bwd Packets": sum(lens(bwd)),
        "Fwd Packet Length Max": max(lens(fwd)) if fwd else 0,
        "Fwd Packet Length Min": min(lens(fwd)) if fwd else 0,
        "Fwd Packet Length Mean": _mean(lens(fwd)),
        "Fwd Packet Length Std": _std(lens(fwd)),
        "Bwd Packet Length Max": max(lens(bwd)) if bwd else 0,
        "Bwd Packet Length Min": min(lens(bwd)) if bwd else 0,
        "Bwd Packet Length Mean": _mean(lens(bwd)),
        "Bwd Packet Length Std": _std(lens(bwd)),
        "Flow Bytes/s": total_bytes / duration_us * 1e6 if duration_us > 0 else 0.0,
        "Flow Packets/s": total_pkts / duration_us * 1e6 if duration_us > 0 else 0.0,
        "Flow IAT Mean": _mean(iats(pkts_sorted)),
        "Flow IAT Std": _std(iats(pkts_sorted)),
        "Flow IAT Max": max(iats(pkts_sorted)) if len(pkts_sorted) > 1 else 0.0,
        "Flow IAT Min": min(iats(pkts_sorted)) if len(pkts_sorted) > 1 else 0.0,
        "Fwd IAT Total": sum(iats(fwd)),
        "Fwd IAT Mean": _mean(iats(fwd)),
        "Fwd IAT Std": _std(iats(fwd)),
        "Fwd IAT Max": max(iats(fwd)) if len(fwd) > 1 else 0.0,
        "Fwd IAT Min": min(iats(fwd)) if len(fwd) > 1 else 0.0,
        "Bwd IAT Total": sum(iats(bwd)),
        "Bwd IAT Mean": _mean(iats(bwd)),
        "Bwd IAT Std": _std(iats(bwd)),
        "Bwd IAT Max": max(iats(bwd)) if len(bwd) > 1 else 0.0,
        "Bwd IAT Min": min(iats(bwd)) if len(bwd) > 1 else 0.0,
        "Fwd Header Length": sum(header_len(it[3]) for it in fwd),
        "Bwd Header Length": sum(header_len(it[3]) for it in bwd),
        "Fwd Packets/s": n_fwd / duration_us * 1e6 if duration_us > 0 else 0.0,
        "Bwd Packets/s": n_bwd / duration_us * 1e6 if duration_us > 0 else 0.0,
        "Min Packet Length": min(l_all),
        "Max Packet Length": max(l_all),
        "Packet Length Mean": _mean(l_all),
        "Packet Length Std": _std(l_all),
        "Packet Length Variance": _std(l_all) ** 2,
        "FIN Flag Count": _flag_count(pkts_sorted, "FIN"),
        "SYN Flag Count": _flag_count(pkts_sorted, "SYN"),
        "RST Flag Count": _flag_count(pkts_sorted, "RST"),
        "PSH Flag Count": _flag_count(pkts_sorted, "PSH"),
        "ACK Flag Count": _flag_count(pkts_sorted, "ACK"),
        "URG Flag Count": _flag_count(pkts_sorted, "URG"),
        "CWE Flag Count": _flag_count(pkts_sorted, "CWE"),
        "ECE Flag Count": _flag_count(pkts_sorted, "ECE"),
        "Down/Up Ratio": (n_bwd / n_fwd) if n_fwd > 0 else 0.0,
        "Average Packet Size": total_bytes / total_pkts if total_pkts else 0.0,
        "Avg Fwd Segment Size": _mean(lens(fwd)),
        "Avg Bwd Segment Size": _mean(lens(bwd)),
        "Init_Win_bytes_forward": _first_win(fwd),
        "Init_Win_bytes_backward": _first_win(bwd),
        "_src_ip": fwd_ep[0],
        "_dst_ip": bwd_ep[0],
        "_first_idx": first_idx,
    }
    return rec


def _port_of(pkt_tuple) -> int:
    """从 (idx, ts, len, ip) 中取 L4 端口（非 tcp/udp 返回 0）。"""
    _, _, _, ip = pkt_tuple
    from scapy.all import TCP, UDP
    if TCP in ip:
        return int(ip[TCP].sport)
    if UDP in ip:
        return int(ip[UDP].sport)
    return 0


def _l4_header_len(ip) -> int:
    from scapy.all import TCP, UDP
    if TCP in ip:
        return int(ip[TCP].dataofs) * 4
    if UDP in ip:
        return 8
    return 0


def _flag_count(pkts_sorted: list, flag: str) -> int:
    """流内出现该 TCP flag 的包数（非 TCP 包计 0）。"""
    from scapy.all import TCP
    bit = _FLAG_BITS[flag]
    return sum(1 for _, _, _, ip in pkts_sorted
               if TCP in ip and int(ip[TCP].flags) & bit)


def _first_win(direction: list) -> int:
    """正向/反向首个 TCP 包的初始窗口（CIC 的 Init_Win_bytes）。"""
    from scapy.all import TCP
    for _, _, _, ip in direction:
        if TCP in ip:
            return int(ip[TCP].window)
    return 0
