import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="最优发货方案工具（自动价格+城市）", layout="wide")

st.title("📦 最优发货方案计算工具（自动读取Excel价格）")

# ------------------------------------------------------
# 1. 装箱容量表
# ------------------------------------------------------
capacity_table = {
    "EV-6":   {"1+2": 18,  "1": 45,  "2": 36},
    "EV-14":  {"1+2": 40,  "1": 80,  "2": 80},
    "EV-32":  {"1+2": 100, "1": 210, "2": 200},
    "EV-60":  {"1+2": 200, "1": 420, "2": 405},
    "EV-96":  {"1+2": 300, "1": 620, "2": 600},
    "EV-128": {"1+2": 340, "1": 700, "2": 680},
}
box_models = list(capacity_table.keys())

# ------------------------------------------------------
# 2. 读取 Excel（缓存）
# ------------------------------------------------------
@st.cache_data
def load_price_excel():
    truck = pd.read_excel("湖州始发精温车子价格.xlsx")
    box = pd.read_excel("湖州始发精温箱价格.xlsx")
    return truck, box

truck_df, box_df = load_price_excel()

# ------------------------------------------------------
# 3. 下拉选择城市
# ------------------------------------------------------
province_list = sorted(truck_df["到达省"].dropna().unique())
province = st.selectbox("选择目的省", province_list)

city_list = sorted(truck_df[truck_df["到达省"] == province]["到达市"].unique())
city = st.selectbox("选择目的市", city_list)

# ------------------------------------------------------
# 4. 输入货物数量
# ------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    qty_1 = st.number_input("A货数量（盒）", 0, step=10)
with col2:
    qty_2 = st.number_input("B货数量（盒）", 0, step=10)

total_qty = qty_1 + qty_2

if total_qty == 0:
    st.warning("请输入货物数量")
    st.stop()

type_key = "1+2" if qty_1 > 0 and qty_2 > 0 else ("1" if qty_1 > 0 else "2")

st.markdown(f"**总盒数：{total_qty}（货物类型：{type_key}）**")

# ------------------------------------------------------
# 5. 通用计算函数
# ------------------------------------------------------
def calc_weight(qty):
    return qty / 100 * 3.6  # 每100盒=3.6kg

# ------------------------------------------------------
# 6. 获取箱子价格
# ------------------------------------------------------
def get_box_price(model):
    row = box_df[
        (box_df["到达省"] == province) &
        (box_df["到达市"] == city)
    ]

    if row.empty:
        return None
    
    return float(row[model].values[0])

# ------------------------------------------------------
# 7. 获取车价格 + 分段收费
# ------------------------------------------------------
def calc_truck_cost(weight, row):
    low = row["最低收费"]

    if weight <= 20:
        unit = row["1-20KG"]
    elif weight <= 50:
        unit = row["20-50KG"]
    elif weight <= 100:
        unit = row["50-100KG"]
    elif weight <= 500:
        unit = row["100-500KG"]
    else:
        unit = row[">500KG"]

    cost = weight * unit
    return max(cost, low)

def get_truck_price(truck_type, weight):
    row = truck_df[
        (truck_df["到达省"] == province) &
        (truck_df["到达市"] == city) &
        (truck_df["重量类型"] == truck_type)
    ]

    if row.empty:
        return None

    return calc_truck_cost(weight, row.iloc[0])

# ------------------------------------------------------
# 8. 箱子方案
# ------------------------------------------------------
def generate_box_plans():
    plans = []

    for model in box_models:
        cap = capacity_table[model][type_key]
        price = get_box_price(model)
        if price is None:
            continue

        need = math.ceil(total_qty / cap)
        cost = need * price

        plans.append({
            "方案类型": "箱子",
            "方式": f"{model}",
            "箱子数": need,
            "车": "无",
            "总费用": cost
        })
    return plans

# ------------------------------------------------------
# 9. 车方案
# ------------------------------------------------------
def generate_truck_plans():
    plans = []
    weight = calc_weight(total_qty)

    for t in truck_df["重量类型"].unique():
        cost = get_truck_price(t, weight)
        if cost is None:
            continue

        plans.append({
            "方案类型": "整车",
            "方式": f"{t} 冷链车",
            "箱子数": 0,
            "车": t,
            "总费用": cost
        })
    return plans

# ------------------------------------------------------
# 10. 混合方案
# ------------------------------------------------------
def generate_mix_plans():
    plans = []

    for model in box_models:
        cap = capacity_table[model][type_key]
        box_price = get_box_price(model)
        if box_price is None:
            continue

        max_boxes = total_qty // cap

        for n in range(1, max_boxes + 1):
            remain = total_qty - n * cap
            weight = calc_weight(remain)

            for t in truck_df["重量类型"].unique():
                truck_cost = get_truck_price(t, weight)
                if truck_cost is None:
                    continue

                total_cost = n * box_price + truck_cost

                plans.append({
                    "方案类型": "混合",
                    "方式": f"{model} × {n} + {t} 车",
                    "箱子数": n,
                    "车": t,
                    "总费用": total_cost
                })
    return plans

# ------------------------------------------------------
# 11. 计算按钮
# ------------------------------------------------------
if st.button("计算最优方案"):
    all_plans = []
    all_plans += generate_box_plans()
    all_plans += generate_truck_plans()
    all_plans += generate_mix_plans()

    df = pd.DataFrame(all_plans)
    df = df.sort_values("总费用").reset_index(drop=True)

    st.success("计算完成！以下为全部方案（已按费用排序）")
    st.dataframe(df)

    st.subheader("🏆 最优方案")
    st.write(df.iloc[0])
