# 模型实验记录

## 运行环境（固定，保证可复现）
- 硬件：13th Gen Intel Core i5-13500H / 15.7 GB 内存
- Python 3.12.5 | scikit-learn 1.5.2 | pandas 2.2.3 | numpy 2.0.2
- random_state = 42
- 划分：train_test_split(test_size=0.2, stratify=y)
- 训练命令（cwd=backend/）：`python -m ml.train --data ml/data/KDDTrain+.csv --test ml/data/KDDTest+.csv`

## 数据集快照
- 名称：NSL-KDD（KDDTrain+ 训练 / KDDTest+ 跨集测试），来源 GitHub 镜像 Matheus-Schmitz/Autoencoder_Hack_Detection（原始出处 UNB，见 DATASET.md 待建）
- 总样本：125,973｜正常：67,343｜攻击：58,630｜比例 1 : 1.15
- 特征数：41（3 个类别列 protocol_type/service/flag 经 OneHot，38 数值列）
- 标签二值化：attack_name == "normal" → 0，其余 → 1

## 基线（必须有，否则精度无意义）

| 基线策略 | Acc | 说明 |
|---|---|---|
| 全猜多数类（随机划分的测试集） | 0.5346 | 若模型只比这个高一点点，说明没学会 |
| 全猜多数类（官方 KDDTest+） | 0.5692 | 跨集口径的基线 |
| 随机猜测 | 0.500 | 二分类参考下界 |

## 实验记录

| 日期 | 模型 | 特征数 | 样本量(正/负) | Acc | Prec | Rec | F1 | AUC | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-11 | RF 默认参数（随机划分 test 20%） | 41 | 13469/11726 | 0.9989 | 0.9995 | 0.9982 | 0.9988 | 1.0000 | 同分布内插，数字虚高；已按规则8排查泄漏（重复行仅16/125973、无单列完美推出label、特征重要性无异常主导列），确认非泄漏，属 NSL-KDD 样本模式化所致 |
| 2026-10-11 | RF 默认参数（官方 KDDTest+ 跨集） | 41 | 9711/12833 | 0.7691 | 0.9684 | 0.6144 | 0.7518 | 0.9600 | **真实泛化口径**；攻击召回仅 61.4%（4948 条攻击漏报），KDDTest+ 含训练集未见攻击类型，跨集掉分是 NSL-KDD 文献公认现象 |
| — | RF class_weight=balanced | — | 同上 | 【未跑】 | — | — | — | — | 未触发：训练集分布 1:1.15 低于脚本设定的 1.5:1 干预阈值，按规则4"先打印分布再决定"自动不干预 |

> 规则：坏结果也必须记。弃用的模型是"我对比过多种方案"的证据，删掉就等于没做对比实验。

## FINAL（写进摘要、结论、PPT 的数字，定型后不许改）
Acc=0.7691, F1=0.7518, AUC=0.9600, throughput=14655条/秒

> 口径声明：FINAL 采用官方 KDDTest+ 跨集评估口径（用户 2026-10-11 确认选项 A，见 DECISIONS.md）。同分布随机划分口径（Acc=0.9989）仅作对照写入设计文档泛化分析章节，不进摘要。F1 取 Attack 类。
> throughput 实测口径（2026-10-11 D4）：KDDTest+ 全量 22,544 条批量推理，预热后连测 3 轮（27627/14655/14370 条/秒），取中位数 14655；含 DataFrame 构造时间，属保守值。测量机 i5-13500H/15.7GB。

---

## V2-PRODUCT 实验区（product 分支，非项目口径，项目 FINAL 不受影响）

### 数据集快照（v2）
- 名称：CIC-IDS2017 MachineLearningCVE（8 份官方 CSV，GitLab 镜像下载，来源记 DECISIONS.md）
- 读入 2,830,743 行；清洗剔除 2,867 行（NaN/Inf=CICFlowMeter 除零产物、超 float32 上限大数，如实计数打印）
- 有效 2,827,876 行：Normal 2,271,320 / Attack 556,556（约 1 : 0.245，攻击占 19.68%）
- 特征 78 列（CICFlowMeter 流特征，全数值）；label 二值化 BENIGN→0 其余→1
- 训练命令（cwd=backend/）：`python -m ml.train_v2`（全量，2026-10-12 17:28 完成）

### v2 基线
| 基线策略 | Acc | 说明 |
|---|---|---|
| 全猜多数类（Normal） | 0.8032 | 攻击全漏，acc=正常占比 |

### v2 实验（同分布切分：train 2,262,300 / test 565,576，stratify，random_state=42）

| 模型 | Acc | Prec(Attack) | Rec(Attack) | F1(Attack) | AUC | 训练耗时 | 推理吞吐 |
|---|---|---|---|---|---|---|---|
| RandomForest（n=100, balanced_subsample） | 0.9989 | 0.9972 | 0.9974 | 0.9973 | 0.9998 | 107s | 292,923 条/秒 |
| **HistGradientBoosting（iter=200, balanced）胜者** | 0.9987 | 0.9937 | **0.9996** | 0.9967 | 0.9998 | 31s | 241,413 条/秒 |

> 胜者规则：召回优先（V2 目标少漏攻击），同分看 F1。HistGB 召回 0.9996 > RF 0.9974，落盘为 model_v2.pkl。
> 指标 >99.5% 属同分布切分口径（规则8 如实提示）：train/test 同源随机切分，不代表跨集/跨网络泛化；产品页与演示须注明。

### v2 阈值扫描（test 565,576 行，recall ≥ 0.90 目标）

| 阈值 | Acc | Prec | Rec | F1 |
|---|---|---|---|---|
| 0.05（调优器推荐：召回最大化的最低阈值） | 0.9973 | 0.9866 | 0.9999 | 0.9932 |
| **0.50（产品部署取值）** | 0.9987 | 0.9937 | 0.9996 | 0.9967 |
| 0.75 | 0.9989 | 0.9960 | 0.9983 | 0.9972 |
| 0.90 | 0.9988 | 0.9967 | 0.9973 | 0.9970 |
| 0.95 | 0.9983 | 0.9973 | 0.9942 | 0.9958 |

> 完整 19 档扫描表见 ml/artifacts/threshold_v2.json。0.05~0.95 全程召回 ≥0.994（目标 0.90 全程达成）。
> 部署取 0.5 而非推荐 0.05 的理由与代价见 DECISIONS.md 2026-10-12 阈值条目。

### V2-PRODUCT FINAL（产品页/README 引用，非项目摘要）
HistGB：Acc=0.9987, Recall(Attack)=0.9996, F1=0.9967, AUC=0.9998（同分布口径），决策阈值=0.5，告警置信门槛=0.90

### v2 推理冒烟（2026-10-12 实测）
- 合成全零特征记录 1 条 → Normal（置信度 0.9993）
- Wednesday CSV 前 3 行（BENIGN 流）→ 全部 Normal（置信度 0.9994~0.9998）

### v2 端到端全链路实测（2026-10-12 阶段F，三脚本合计 30 项通过，跑完即删）
- **v2 csv 检测**：Wednesday 抽样 200 行（100 BENIGN + 100 攻击）上传→success，total=200 attack=99 normal=101，cost_seconds=2.148s，stats 三数一致（200）
- **攻击识别率**：99/100 攻击行被判定 Attack（1 条漏判/特征退化，同分布样本内）
- **告警链路**：高置信（≥0.90）Attack 行去重后落库 92 条 open（99 命中去重到 92 独立源）；ack 200、重复 ack 400、dismiss 200、count 递减 92→90、无 token 访问 401
- **MachineLearningCVE 无 Source IP 列**：该格式告警 src_key 回退行引用（row-N）并给人工复核文案——设计内行为（models.py 注释）
- **pcap 链路**：scapy 合成 pcap（1 条 SYN 流 + 1 条 UDP 双向流）上传→success，流提取 2 条 cost=1.606s；纯 SYN 合成流判 Normal（良性特征输出，非链路缺陷）
- **generate_alerts IP 分支**：3 命中同源去重→2 条落库，置信度降序，src_key=IPv4 全部生成 New-NetFirewallRule 命令，count=2
- **webhook**（本地 HTTPServer 接收实测）：generic {"text"} 与 feishu {"msg_type":"text"} 格式均送达 200；目标不可达仅 warning 不抛异常；URL 空=不外发
