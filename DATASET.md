# 数据集档案

## NSL-KDD（当前使用）
- 用途：模型训练与评估（D3/D4）
- 来源：GitHub 镜像 `https://raw.githubusercontent.com/Matheus-Schmitz/Autoencoder_Hack_Detection/master/data/KDDTrain.csv`（原始出处：加拿大网络安全研究所 UNB，http://www.unb.ca/cic/datasets/nsl.html）
- 获取日期：2026-10-11
- 本地路径：`backend/ml/data/KDDTrain+.csv`（125,973 行 / 13.6MB）、`backend/ml/data/KDDTest+.csv`（22,544 行）
- 格式：无表头 CSV，42 列 = 41 特征 + 攻击名（最后一列）；列名清单硬编码在 `backend/ml/train.py` 的 NSL_KDD_COLUMNS
- 标签处理：attack_name == "normal" → 0，其余 → 1（二分类）
- 分布：正常 67,343 / 攻击 58,630（1:1.15）
- 局限性（设计文档需声明）：
  - 数据源自 1999 KDD Cup 99 的去重修订版，攻击类型不含现代攻击（无加密勒索、APT 等）
  - KDDTest+ 含训练集未见攻击族，跨集精度显著低于同分布划分（见 METRICS.md 实验记录）
  - DECISIONS.md 2026-09-21 已记录：放弃 CIC-IDS2018 全量（几十 GB，新手环境跑不动）
- 合规声明：仅用于离线研究与教学演示，数据本身不含真实受害者流量
