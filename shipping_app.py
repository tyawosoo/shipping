import streamlit as st
import pulp
import pandas as pd

st.title("最优发货方案计算工具")

# 输入发货数量
Q = st.number_input("请输入发货数量（支）", min_value=1, value=400)

st.write("请填写运输方式的参数（可自由添加行）：")

# 默认运输方式数据
default_data = {
    "运输方式": ["箱子", "小车", "冷链车"],
    "容量(支)": [40, 500, 4000],
    "成本(元)": [20, 80, 600]
}

# 可编辑表格
df = st.data_editor(pd.DataFrame(default_data), num_rows="dynamic")
st.write("可直接修改容量和成本，如需添加新的运输方式可增加一行。")

if st.button("计算最优发货方案"):
    modes = df.to_dict(orient="records")

    # 构建最优化模型
    model = pulp.LpProblem("shipping", pulp.LpMinimize)

    # 决策变量：每种运输方式的数量（整数）
    x = {
        m["运输方式"]: pulp.LpVariable(m["运输方式"], lowBound=0, cat="Integer")
        for m in modes
    }

    # 约束：总容量需覆盖发货数量 Q
    model += sum(x[m["运输方式"]] * m["容量(支)"] for m in modes) >= Q

    # 目标：总成本最小
    model += sum(x[m["运输方式"]] * m["成本(元)"] for m in modes)

    # 开始求解
    model.solve()

    st.subheader("最优方案（只显示数量大于 0 的运输方式）：")

    results = []
    total_cost = 0

    for m in modes:
        name = m["运输方式"]
        num = int(x[name].value())
        if num > 0:
            results.append({
                "运输方式": name,
                "数量": num,
                "总容量": num * m["容量(支)"],
                "总成本": num * m["成本(元)"]
            })
            total_cost += num * m["成本(元)"]

    # 输出结果表格
    if len(results) > 0:
        st.dataframe(pd.DataFrame(results))
    else:
        st.write("⚠ 模型返回零解，请检查运输方式数据是否正确。")

    st.write(f"### 总成本：{total_cost} 元")

    total_capacity = sum(r["总容量"] for r in results)
    st.write(f"### 总运力：{total_capacity} 支（需求：{Q} 支）")
