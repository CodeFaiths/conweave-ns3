# 分析脚本对比说明

## autoAnalyze.sh vs quick_analyze.sh

### autoAnalyze.sh（新版 - 推荐使用）

**特点：**
- ✅ **全面覆盖**：集成了所有分析功能，包括新增的吞吐量和链路利用率监控
- ✅ **智能检测**：自动检测并分析所有可用的输出文件
- ✅ **模块化设计**：每个分析可以单独启用/禁用
- ✅ **详细统计**：提供完整的分析完成度统计
- ✅ **灵活配置**：支持更多命令行选项
- ✅ **友好输出**：彩色输出和进度提示

**支持的分析：**
1. ✅ Trace 文件分析（链路利用率与队列长度）
2. ✅ PFC 事件分析（统计汇总与关联分析）
3. ✅ Ingress 队列分析（PFC 触发分析）
4. ✅ Egress 队列长度分析
5. ✅ **吞吐量和链路利用率分析**（新增）
6. ✅ Uplink 监控分析
7. ✅ FCT（Flow Completion Time）分析

**使用场景：**
- 日常实验分析
- 完整的性能评估
- 需要吞吐量和链路利用率数据
- 需要灵活控制分析流程

---

### quick_analyze.sh（原版）

**特点：**
- 轻量级设计
- 专注于核心分析（Trace, PFC, Ingress, Egress）
- 代码简洁
- 适合快速检查

**支持的分析：**
1. ✅ Trace 文件分析
2. ✅ PFC 事件分析
3. ✅ Ingress 队列分析
4. ✅ Link utilization（从 trace 推断）
5. ✅ Egress 队列长度分析

**使用场景：**
- 快速查看基础指标
- 不需要详细吞吐量统计
- 简单场景

---

## 功能对比表

| 功能 | autoAnalyze.sh | quick_analyze.sh |
|------|----------------|------------------|
| Trace 分析 | ✅ | ✅ |
| PFC 分析 | ✅ | ✅ |
| Ingress 队列分析 | ✅ | ✅ |
| Egress 队列分析 | ✅ | ✅ |
| **实时吞吐量监控** | ✅ | ❌ |
| **链路利用率监控** | ✅ | ❌ |
| Uplink 监控 | ✅ | ❌ |
| FCT 分析 | ✅ | ❌ |
| 模块化开关 | ✅ | ❌ |
| 详细统计报告 | ✅ | ❌ |
| 彩色输出 | ✅ | ✅ |
| 端口过滤 | ✅ | ✅ |

---

## 使用建议

### 推荐使用 autoAnalyze.sh，如果你需要：

1. **完整的性能分析**
   ```bash
   ./autoAnalyze.sh
   ```

2. **吞吐量和链路利用率数据**
   ```bash
   ./autoAnalyze.sh  # 自动包含吞吐量分析
   ```

3. **只分析特定端口**
   ```bash
   ./autoAnalyze.sh --include "SW6-P1 SW6-P6"
   ```

4. **跳过不需要的分析以节省时间**
   ```bash
   ./autoAnalyze.sh --skip-trace --skip-pfc  # 只分析吞吐量和队列
   ```

### 使用 quick_analyze.sh，如果你只需要：

1. **快速查看基础指标**
   ```bash
   ./quick_analyze.sh
   ```

2. **不需要吞吐量详细数据**
3. **简单的实验验证**

---

## 迁移指南

如果你之前使用 `quick_analyze.sh`，迁移到 `autoAnalyze.sh` 非常简单：

### 1. 完全替换

原来：
```bash
./quick_analyze.sh
```

现在：
```bash
./autoAnalyze.sh
```

### 2. 保持端口过滤

原来：
```bash
./quick_analyze.sh --include "SW6-P1 SW6-P6"
```

现在：
```bash
./autoAnalyze.sh --include "SW6-P1 SW6-P6"
```

### 3. 如果只需要基础分析（模拟 quick_analyze）

```bash
./autoAnalyze.sh --skip-throughput --skip-uplink --skip-fct
```

---

## 配置要求

### autoAnalyze.sh 额外需要的配置

在 `config.txt` 中添加：

```
# 吞吐量和链路利用率监控（autoAnalyze.sh 新增）
ENABLE_THROUGHPUT_MONITORING 1
ENABLE_LINK_UTIL_MONITORING 1
THROUGHPUT_MON_INTERVAL 10000
THROUGHPUT_MON_FILE mix/CPEMTest/01_Bandwidth_Mismatch/output/out_throughput.txt
LINK_UTIL_MON_FILE mix/CPEMTest/01_Bandwidth_Mismatch/output/out_link_util.txt
```

**注意**：如果不添加这些配置，`autoAnalyze.sh` 会自动跳过吞吐量分析，其他分析不受影响。

---

## 性能对比

| 特性 | autoAnalyze.sh | quick_analyze.sh |
|------|----------------|------------------|
| 执行时间 | ~10-30秒（取决于数据量） | ~5-15秒 |
| 生成图表数量 | 更多（15-25张） | 较少（8-12张） |
| CSV 输出 | 更详细 | 基础统计 |
| 内存占用 | 略高 | 较低 |

---

## 常见问题

### Q: 我应该删除 quick_analyze.sh 吗？

**A**: 不需要。两个脚本可以共存。如果你的某些旧实验没有配置吞吐量监控，`quick_analyze.sh` 仍然有用。

### Q: autoAnalyze.sh 会生成更多文件吗？

**A**: 是的，会额外生成：
- 吞吐量相关图表（4张）
- 链路利用率图表（4张）
- 对应的 CSV 文件

### Q: 可以同时运行两个脚本吗？

**A**: 可以，但不推荐。它们会覆盖同名的输出文件。建议选择其一使用。

### Q: 我的实验没有吞吐量数据，autoAnalyze.sh 会报错吗？

**A**: 不会。脚本会智能检测，如果文件不存在会自动跳过该分析并显示警告。

---

## 总结

- **新实验 → 使用 autoAnalyze.sh**（完整功能 + 吞吐量监控）
- **旧实验 → 继续使用 quick_analyze.sh**（如果没有配置吞吐量监控）
- **灵活使用 → autoAnalyze.sh + --skip-*** 选项**（按需分析）

推荐所有新实验都配置吞吐量监控并使用 `autoAnalyze.sh`，以获得最全面的性能数据！
