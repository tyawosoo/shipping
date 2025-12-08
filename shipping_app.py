import streamlit as st
import pandas as pd
import math
import numpy as np

st.set_page_config(page_title="最优发货方案工具", layout="wide")
st.title("📦 最优发货方案工具")

# -------------------------

# 上传 Excel

# -------------------------

st.sidebar.header("上传 Excel 文件")
car_file = st.sidebar.file_uploader("上传车价 Excel", type=["xlsx"])
box_file = st.sidebar.file_uploader("上传箱子 Excel", type=["xlsx"])

if car_file is None or box_file is None:
st.warning("请上传车价和箱子 Excel 文件")
st.stop()

car_df = pd.read_excel(car_file)
box_df = pd.read_excel(box_file)

# -------------------------

# 用户输入

# -------------------------

st.subheader("选择线路和数量")
start_city = st.selectbox("始发市", sorted(car_df["始发市"].unique()))
end_city = st.selectbox("到达市", sorted(car_df["到达市"].unique()))
a_qty = st.number_input("A货数量（盒）", min_value=0, value=100)
b_qty = st.number_input("B货数量（盒）", min_value=0, value=100)

total_boxes = int(a_qty + b_qty)
st.write(f"总箱数：**{total_boxes}**（货物类型：{'1+2' if a_qty>0 and b_qty>0 else '1' if a_qty>0 else '2'}）")

# -------------------------

# 箱子信息

# -------------------------

capacity_table = {
"EV-6": 18,
"EV-14": 40,
"EV-32": 100,
"EV-60": 200,
"EV-96": 300,
"EV-128": 340
}
box_models = list(capacity_table.keys())

# 去除空格

box_df = box_df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

# -------------------------

# 辅助函数

# -------------------------

def get_box_price(box_type):
row = box_df[(box_df["始发市"]==start_city) & (box_df["到达市"]==end_city)]
if row.empty:
return None
return float(row.iloc[0][box_type])

def get_car_price(total_weight):
row = car_df[(car_df["始发市"]==start_city) & (car_df["到达市"]==end_city)]
if row.empty:
return None
weight = total_weight
if weight <=20:
unit = float(row.iloc[0]["1-20KG"])
elif weight<=50:
unit = float(row.iloc[0]["20-50KG"])
elif weight<=100:
unit = float(row.iloc[0]["50-100KG"])
elif weight<=500:
unit = float(row.iloc[0]["100-500KG"])
else:
unit = float(row.iloc[0][">500KG"])
cost = max(weight*unit, float(row.iloc[0]["最低收费元/票"]))
return cost

def solve_box_combination(total_boxes):
# 完全背包动态规划：dp[i] = 最小费用, path[i]=最后一个选择箱型
dp = [float('inf')] * (total_boxes+1)
path = [-1]*(total_boxes+1)
dp[0] = 0
for i in range(1,total_boxes+1):
for box in box_models:
cap = capacity_table[box]
price = get_box_price(box)
if price is None or cap>i:
continue
if dp[i-cap]+price < dp[i]:
dp[i] = dp[i-cap]+price
path[i] = box
if dp[total_boxes]==float('inf'):
return None
# 反推组合
res = {}
i = total_boxes
while i>0:
box = path[i]
if box not in res:
res[box]=0
res[box]+=1
i -= capacity_table[box]
return res, dp[total_boxes]

# -------------------------

# 计算方案

# -------------------------

if st.button("计算最优方案"):
results = []

```
# 1️⃣ 整车方案
total_weight = total_boxes*0.036*1  # 100盒3.6kg
car_cost = get_car_price(total_weight)
if car_cost is not None:
    results.append({"方案类型":"整车","方式":"整车运输","箱子数":0,"车":1,"总费用":car_cost})

# 2️⃣ 纯箱子方案（混合）
box_comb, box_cost = solve_box_combination(total_boxes)
if box_comb is not None:
    label = " + ".join([f"{k}×{v}" for k,v in box_comb.items()])
    results.append({"方案类型":"箱子","方式":label,"箱子数":total_boxes,"车":0,"总费用":box_cost})

# 3️⃣ 混合方案（可选，如果你想混合部分车 + 箱子）
# 这里因为车按重量计费，可以理解为箱子剩余部分用车运输
# 我们可以尝试每种箱子数量组合，剩余重量用车
# 为简单，可枚举每种箱子数1~total_boxes
for box_type in box_models:
    price = get_box_price(box_type)
    if price is None:
        continue
    cap = capacity_table[box_type]
    max_count = math.ceil(total_boxes/cap)
    for n in range(1,max_count):
        remain_boxes = total_boxes - n*cap
        remain_weight = remain_boxes*0.036
        remain_car_cost = get_car_price(remain_weight)
        if remain_car_cost is None:
            continue
        total_cost = n*price + remain_car_cost
        results.append({
            "方案类型":"混合",
            "方式":f"{box_type}×{n} + 剩余用车",
            "箱子数":n,
            "车":remain_weight,
            "总费用":total_cost
        })

if len(results)==0:
    st.error("没有可行方案，请检查 Excel 数据")
    st.stop()

df = pd.DataFrame(results)
df = df.sort_values("总费用").reset_index(drop=True)

st.success("计算完成，方案如下（已按总费用升序排序）")
st.dataframe(df)

st.subheader("🏆 最优方案")
st.write(df.iloc[0])

# 显示箱子单价调试
price_debug = {box:get_box_price(box) if get_box_price(box) is not None else "无" for box in box_models}
st.write("箱子单价（若为无表示该城市/省无数据）：",price_debug)
```

