import matplotlib.pyplot as plt
import numpy as np
import os

# 设置文件路径
input_file = '/home/rdmauser/users/jiangtao/ns-allinone-3.19/ns-3.19/mix/CPEMTest/02_Incast_Congestion/output/slowdown.txt'
output_dir = '/home/rdmauser/users/jiangtao/ns-allinone-3.19/ns-3.19/mix/CPEMTest/02_Incast_Congestion/analyze/figures'
output_file = os.path.join(output_dir, 'algorithm_slowdown_cmp.png')

# 确保输出目录存在
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def plot_slowdown():
    algorithms = []
    flow_types = []
    data = []

    # 读取并解析文档数据
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

        # 解析第一行（Header）
        header_line = lines[0]
        # 考虑到 "Flow type" 和 "DCQCN" 之间可能是大量空格而非 Tab
        import re
        # 使用正则表达式分割，匹配一个或多个 Tab 或 多个空格（至少2个）
        header_parts = re.split(r'\t+| {2,}', header_line)
        # 排除第一项 "Flow type"
        algorithms = [alg.strip().replace('（', '(').replace('）', ')') for alg in header_parts[1:]]

        # 后续行是各个流类型的具体数据
        for line in lines[1:]:
            # 数据行通常是用 Tab 分隔的
            parts = re.split(r'\t+', line)

            flow_type = parts[0].strip()
            # 获取数值部分
            values = [float(val) for val in parts[1:] if val.strip()]

            # 确保 values 长度与 algorithms 匹配
            if len(values) == len(algorithms):
                flow_types.append(flow_type)
                data.append(values)
            else:
                print(f"警告: 行 '{flow_type}' 的数据列数 ({len(values)}) 与算法数 ({len(algorithms)}) 不匹配，已跳过。")

    # 绘图配置
    x = np.arange(len(flow_types))  # 流类型位置
    width = 0.1  # 柱子宽度

    fig, ax = plt.subplots(figsize=(14, 8))

    # 为每种算法画一组柱子
    bars = []
    for i, alg_name in enumerate(algorithms):
        alg_values = [row[i] for row in data]
        offset = (i - len(algorithms)/2 + 0.5) * width
        rects = ax.bar(x + offset, alg_values, width, label=alg_name)
        bars.append(rects)

    # 在每组表现最好的柱状图上打五角星（Slowdown 越小越好）
    for j in range(len(flow_types)):
        # 找到当前流类型中表现最好的值（最小值）
        row_values = data[j]
        min_val = min(row_values)
        min_indices = [i for i, v in enumerate(row_values) if v == min_val]

        for idx in min_indices:
            # 获取对应的柱子
            rect = bars[idx][j]
            height = rect.get_height()
            # 在柱子顶部标注星号
            ax.text(rect.get_x() + rect.get_width()/2., height + 0.05, '★',
                    ha='center', va='bottom', color='red', fontsize=20, fontweight='bold')

    # 添加文本说明
    ax.set_ylabel('FCT Slowdown')
    ax.set_title('Incast Congestion: FCT Slowdown Comparison by Flow Type')
    ax.set_xticks(x)
    ax.set_xticklabels(flow_types)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()

    # 保存结果
    plt.savefig(output_file, dpi=300)
    print(f"成功生成对比图: {output_file}")

if __name__ == "__main__":
    try:
        plot_slowdown()
    except Exception as e:
        print(f"绘图过程中出错: {e}")
