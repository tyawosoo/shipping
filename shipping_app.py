import streamlit as st
import pandas as pd
import itertools
import math

st.set_page_config(page_title="最优发货方案工具", layout="wide")
st.title("📦 最优发货方案工具（自动读取 Excel 价格，多方案对比）")

# -------------------------
# 读取 Excel 文件
# -------------------------
@st.cache_data
def load_data():
    truck_df = pd.read_excel("湖州始发精温车子价格.xlsx")
    box_df = pd.read_excel("湖州始发精温箱价格.xlsx")
    return truck_df, box_df

truck_df, box_df = load_data()

# -------------------------
# 容量表（固定）
# -------------------------
capacity_table = {
    "EV-6":   {"1+2": 18,  "1": 45,  "2": 36},
    "EV-14":  {"1+2": 40,  "1": 80,  "2": 80},
    "EV-32":  {"1+2": 100, "1": 210, "2": 200},
    "EV-60":  {"1+2": 200, "1": 420, "2": 405},
    "EV-96":  {"1+2": 300, "1": 620, "2": 600},
    "EV-128": {"1+2": 340, "1": 700, "2": 680},
}

# -------------------------
# UI 输入项
# -------------------------
province_list = sorted(box_df["到达省"].unique())
province = st.selectbox("选择目的省", province_list)

city_list = sorted(box_df[box_df["到达省"] == province]["到达市"].unique())
city = st.selectbox("选择目的城市", city_list)

col1, col2 = st.columns(2)
A = col1.number_input("A 货数量（盒）", min_value=0, value=100)
B = col2.number_input("B 货数量（盒）", min_value=0, value=100)

total_units = A + B
st.write(f"### 总盒数：{total_units} 盒")

# 货物类型：1 / 2 / 1+2
if A > 0 and B > 0:
    cargo_type = "1+2"
elif A > 0:
    cargo_type = "1"
else:
    cargo_type = "2"

# -------------------------
# 获取箱子单价
# -------------------------
def get_box_prices(province, city):
    row = box_df[(box_df["到达省"] == province) & (box_df["到达市"] == city)]
    if row.empty:
        return None
    return {
        "EV-6": row["EV-6"].values[0],
        "EV-14": row["EV-14"].values[0],
        "EV-32": row["EV-32"].values[0],
        "EV-60": row["EV-60"].values[0],
        "EV-96": row["EV-96"].values[0],
        "EV-128": row["EV-128"].values[0],
    }

# -------------------------
# 获取整车价格
# -------------------------
def get_truck_price(province, city, weight):
    row = truck_df[(truck_df["到达省"] == province) & (truck_df["到达市"] == city)]
    if row.empty:
        return None

    base = row["最低收费"].values[0]

    if weight <= 20:
        price = row["1-20KG"].values[0] * weight
    elif weight <= 50:
        price = row["20-50KG"].values[0] * weight
    elif weight <= 100:
        price = row["50-100KG"].values[0] * weight
    elif weight <= 500:
        price = row["100-500KG"].values[0] * weight
    else:
        price = row[">500KG"].values[0] * weight

    return max(base, price)

# -------------------------
# 计算纯箱子方案（箱子可混用）
# -------------------------
def generate_box_only_plans(total_units, cargo_type, box_prices):
    plans = []

    # 所有箱型组合（允许任意数量）
    box_models = list(capacity_table.keys())

    # 遍历不同的组合深度
    for r in range(1, 4):  # 最多用 3 种型号组合，提高速度
        for combo in itertools.combinations_with_replacement(box_models, r):
            # 使用容量最大优先装
            capacity_sorted = sorted(combo, key=lambda x: capacity_table[x][cargo_type], reverse=True)

            remain = total_units
            detail = {}
            total_cost = 0

            for model in capacity_sorted:
                cap = capacity_table[model][cargo_type]
                count = remain // cap
                if count > 0:
                    detail[model] = count
                    remain -= count * cap
                    total_cost += count * box_prices[model]

            # 剩余部分用最小箱子装
            if remain > 0:
                small = "EV-6"
                count = math.ceil(remain / capacity_table[small][cargo_type])
                detail[small] = detail.get(small, 0) + count
                total_cost += count * box_prices[small]
                remain = 0

            plans.append({
                "方案类型": "纯箱子",
                "组成": detail,
                "费用": total_cost
            })

    return plans

# -------------------------
# 计算整车方案
# -------------------------
def generate_truck_only_plan(total_units, province, city):
    weight = total_units / 100 * 3.6
    price = get_truck_price(province, city, weight)
    if price is None:
        return []
    return [{
        "方案类型": "整车",
        "组成": {"整车": 1},
        "费用": price
    }]

# -------------------------
# 计算混合方案（先箱子，再车；或先车，再箱子）
# -------------------------
def generate_mixed_plans(total_units, cargo_type, province, city, box_prices):
    plans = []

    # 遍历 0% ~ 70% 箱子占比
    for ratio in [0.2, 0.4, 0.6]:
        box_part = int(total_units * ratio)
        truck_part = total_units - box_part

        # 箱子部分
        box_plans = generate_box_only_plans(box_part, cargo_type, box_prices)
        best_box = min(box_plans, key=lambda x: x["费用"])

        # 车部分
        weight = truck_part / 100 * 3.6
        truck_price = get_truck_price(province, city, weight)

        if truck_price:
            plans.append({
                "方案类型": "车 + 箱子",
                "组成": {"车重量盒数": truck_part, "箱子明细": best_box["组成"]},
                "费用": best_box["费用"] + truck_price
            })

    return plans

# -------------------------
# 主执行逻辑
# -------------------------
if st.button("计算最优方案"):
    box_prices = get_box_prices(province, city)

    all_plans = []
    if box_prices:
        all_plans += generate_box_only_plans(total_units, cargo_type, box_prices)

    all_plans += generate_truck_only_plan(total_units, province, city)

    if box_prices:
        all_plans += generate_mixed_plans(total_units, cargo_type, province, city, box_prices)

    # 按价格升序
    all_plans = sorted(all_plans, key=lambda x: x["费用"])

    st.subheader("💡 最优方案（按价格升序）")
    for p in all_plans[:10]:  # 显示前 10 个最优方案
        st.write("### 方案类型：", p["方案类型"])
        st.write("细节：", p["组成"])
        st.write(f"💰 费用：**{p['费用']:.2f} 元**")
        st.write("---")
