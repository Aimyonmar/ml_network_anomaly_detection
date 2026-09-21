
| 日期 | 现象 | 根因 | 解决 | 耗时 | 归属章节 |
|---|---|---|---|---|---|
| 2026-09-21 | （示例）训练准确率 99.8%，明显异常 | StandardScaler 在 split 之前 fit 了全量数据，造成数据泄漏 | 用 Pipeline 包裹，保证先 split 再 fit_transform 训练集 | 1.5h | 5.2 特征工程 |
| 2026-09-21 | （示例）上传大文件报 504 Gateway Timeout | detection 逻辑同步执行，阻塞 worker | 改 BackgroundTasks 异步 + 前端轮询 status | 3h | 5.3 性能优化 |
| 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待填】 |