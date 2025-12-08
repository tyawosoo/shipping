# streamlit_app.py
import streamlit as st
import pandas as pd
import math
import re

st.set_page_config(page_title="最优发货方案工具", layout="wide")
st.title("📦 最优发货方案工具")

# -------------------------
# 容量表（不变）
# -------------------------
capacity_table = {
    "EV-6":   {"1+2": 18,  "1": 45,  "2": 36},
    "EV-14":  {"1+2": 40,  "1": 80,  "2": 80},
    "EV-32":  {"1+2": 100, "1": 210, "2": 200},
    "EV-60":  {"1+2": 200, "1": 420, "2": 405},
    "EV-96":  {"1+2": 300, "1": 620, "2": 600},
    "EV-128": {"1+2": 340, "1": 700, "2": 680},
}
box_models = list(capacity_table.keys())

# -------------------------
# 读取 Excel（缓存）
# -------------------------
@st.cache_data
def load_excels():
    truck_df = pd.read_excel("湖州始发精温车子价格.xlsx")
    box_df = pd.read_excel("湖州始发精温箱价格.xlsx")
    return truck_df, box_df

try:
    truck_df, box_df = load_excels()
except FileNotFoundError as e:
    st.error("找不到 Excel 文件，请确保仓库根目录有：\n- 湖州始发精温车价格.xlsx\n- 湖州始发精温箱子价格.xlsx")
    st.stop()

# -------------------------
# 选择目的地（从 truck_df 自动抽取）
# -------------------------
# 尝试找到到达省/市列名（有很多可能写法），构造函数自动匹配
def find_column(df, candidates):
    """从候选列名列表中返回第一个存在的列名，或者 None"""
    cols = df.columns.astype(str).tolist()
    for c in candidates:
        for col in cols:
            if col.strip().lower() == c.strip().lower():
                return col
    return None

# 常见列名候选（覆盖多种写法）
to_prov_candidates = ["到达省","目的省","到省","province","到达省份","到省份"]
to_city_candidates = ["到达市","目的市","到市","city","到达城市","到城市"]
from_prov_candidates = ["始发省","出发省","始发省份"]
from_city_candidates = ["始发市","出发市","始发城市"]

to_prov_col = find_column(truck_df, to_prov_candidates)
to_city_col = find_column(truck_df, to_city_candidates)

if not to_prov_col or not to_city_col:
    st.error("在车价 Excel 中未找到目的省/市列（列名）。请检查表头，并确保包含到达省/到达市或类似字段。")
    st.write("Truck table columns:", truck_df.columns.tolist())
    st.stop()

province_list = sorted(truck_df[to_prov_col].dropna().unique())
province = st.selectbox("选择目的省", province_list)

city_list = sorted(truck_df[truck_df[to_prov_col] == province][to_city_col].dropna().unique())
city = st.selectbox("选择目的市", city_list)

# -------------------------
# 输入数量
# -------------------------
col1, col2 = st.columns(2)
with col1:
    qty_1 = st.number_input("A货数量（盒）", 0, step=1, value=0)
with col2:
    qty_2 = st.number_input("B货数量（盒）", 0, step=1, value=0)

total_qty = int(qty_1 + qty_2)
if total_qty <= 0:
    st.warning("请输入要运输的货物数量（A 或 B 或两者）")
    st.stop()

type_key = "1+2" if qty_1 > 0 and qty_2 > 0 else ("1" if qty_1 > 0 else "2")
st.markdown(f"**总盒数：{total_qty}（货物类型：{type_key}）**")

# -------------------------
# 辅助：找箱子价格
# -------------------------
# box_df 列可能包含 EV-6, EV-14 ... 或用别名；先找到列名里包含 EV 的列
box_cols = [c for c in box_df.columns.astype(str) if re.search(r'EV[\s\-_]?6|EV[\s\-_]?14|EV[\s\-_]?32|EV[\s\-_]?60|EV[\s\-_]?96|EV[\s\-_]?128', c, re.I)]
# 找到到达列（与 truck 相同的候选）
box_to_prov = find_column(box_df, to_prov_candidates)
box_to_city = find_column(box_df, to_city_candidates)

if not box_to_prov or not box_to_city:
    st.warning("箱子价格表未找到到达省/市列（会跳过箱子匹配）。")
else:
    # 过滤到当前目的地行
    box_row = box_df[(box_df[box_to_prov] == province) & (box_df[box_to_city] == city)]
    # box_row 可能为空，后续代码会检测

# -------------------------
# 辅助：在 truck_df 中识别“最低收费”与各重量区间列
# -------------------------
# 我们在 truck_df 的列中寻找最小费和区间单价列
cols = truck_df.columns.astype(str).tolist()

# 最低收费列候选
min_fee_candidates = ["最低收费","最低","min_fee","min charge","最低收取","最低价格"]
min_fee_col = None
for col in cols:
    low = col.lower().replace(" ", "")
    for c in min_fee_candidates:
        if c.replace(" ", "") in low:
            min_fee_col = col
            break
    if min_fee_col:
        break

# 重量区间候选（寻找包含数字区间的列）
weight_bands = {}
# 我们定义目标区间边界和候选关键词
bands = [("1-20", (1,20)), ("20-50", (20,50)), ("50-100", (50,100)), ("100-500", (100,500)), (">500", (500, None))]
band_col_map = {}
for col in cols:
    col_norm = col.lower().replace(" ", "").replace("kg","")
    # 查找 1和20
    for key, rng in bands:
        # try common representations
        patterns = [
            key.replace("-", ""),
            key.replace("-", "_"),
            key,
            key.replace("-", "–"),
            key.replace("-", "—"),
            key.replace("-", "to"),
            key.replace("-", "")
        ]
        for p in patterns:
            if p in col_norm:
                band_col_map[key] = col
                break

# 如果没有找到任何带数字的区间列，尝试根据列头是否为具体数字（例如 "1-20KG" 之类）
# done above; band_col_map 可能为空 -> handle later

# -------------------------
# 计算重量
# -------------------------
def calc_weight(qty):
    return qty / 100.0 * 3.6

# 通用：从匹配行中读取箱子价格（若无数据返回 None）
# 替换原来的 get_box_price_for 函数为这个更健壮的版本
def get_box_price_for(model):
    if not box_to_prov or not box_to_city or not box_cols:
        return None
    # 先尝试市级匹配
    row_city = box_df[(box_df[box_to_prov] == province) & (box_df[box_to_city] == city)]
    def extract_price_from_row(row):
        for col in box_cols:
            # 忽略大小写、空格，按模型名匹配列
            if re.search(model.replace("-", "").lower(), col.replace(" ", "").lower()):
                try:
                    v = row[col]
                    if pd.isna(v):
                        return None
                    return float(v)
                except Exception:
                    return None
        return None

    if not row_city.empty:
        v = extract_price_from_row(row_city.iloc[0])
        if v is not None:
            return v

    # 市级没有，尝试省级（退回到省级价格）
    row_prov = box_df[(box_df[box_to_prov] == province)]
    if not row_prov.empty:
        # 如果存在多行省级数据，先取第一行非空的价格
        for idx, r in row_prov.iterrows():
            v = extract_price_from_row(r)
            if v is not None:
                return v

    # 如果仍然没找到，返回 None
    return None

# 计算某一行（pandas Series）的车费，行需包含最低收费与区间单价列或近似列
def calc_truck_cost_from_row(weight, row):
    # 找最低收费
    low = None
    if min_fee_col and min_fee_col in row:
        try:
            low = float(row[min_fee_col])
        except:
            low = None

    # 找区间单价（匹配 band_col_map 的列）
    unit = None
    # 根据 weight 决定使用哪个区间 key
    if weight <= 20:
        band_key = "1-20"
    elif weight <= 50:
        band_key = "20-50"
    elif weight <= 100:
        band_key = "50-100"
    elif weight <= 500:
        band_key = "100-500"
    else:
        band_key = ">500"

    # 如果 band_col_map 找到对应列，直接读取
    if band_key in band_col_map:
        colname = band_col_map[band_key]
        try:
            unit = float(row[colname])
        except:
            unit = None

    # 如果没找到 unit，尝试从 row 中找近似数字列（例如列名包含 '1' and '20' 等）
    if unit is None:
        for col in row.index:
            name = str(col).lower()
            # 寻找包含 '1' '20' 或 '20' '50' 的列名
            if band_key.replace("-", "") in name.replace(" ", ""):
                try:
                    unit = float(row[col])
                    break
                except:
                    pass

    # 如果仍然没有 unit，就返回 None（表示这行不能用于计费）
    if unit is None:
        return None

    cost = weight * unit
    if low is not None:
        try:
            cost = max(cost, float(low))
        except:
            pass
    return float(cost)

# -------------------------
# 生成方案：箱子方案、整车方案、混合方案
# -------------------------
def generate_box_plans():
    plans = []
    for model in box_models:
        cap = capacity_table[model][type_key]
        price = get_box_price_for(model)
        if price is None:
            continue
        need = math.ceil(total_qty / cap)
        cost = need * price
        plans.append({"方案类型":"箱子","方式":model,"箱子数":need,"车":"无","总费用":cost})
    return plans

def generate_truck_plans():
    plans = []
    weight = calc_weight(total_qty)
    # 过滤出匹配目的地的行（所有可能的车型 / 方案行）
    rows = truck_df[(truck_df[to_prov_col] == province) & (truck_df[to_city_col] == city)]
    if rows.empty:
        return plans
    # 对每一行尝试计算车费（行内可能代表一种车型或一种流向）
    for idx, row in rows.iterrows():
        cost = calc_truck_cost_from_row(weight, row)
        if cost is None:
            continue
        # 生成一个可读的车型标识：优先取 '流向类型' 或 '车型' 或其他列
        label = None
        for cand in ["流向类型","车型","重量类型","运输方式"]:
            if cand in row.index and not pd.isna(row[cand]):
                label = str(row[cand])
                break
        if label is None:
            # fallback 用行号或组合字段
            label = f"方案-{idx}"
        plans.append({"方案类型":"整车","方式":label,"箱子数":0,"车":label,"总费用":float(cost)})
    return plans

def generate_mix_plans():
    plans = []
    rows = truck_df[(truck_df[to_prov_col] == province) & (truck_df[to_city_col] == city)]
    if rows.empty:
        return plans
    for model in box_models:
        cap = capacity_table[model][type_key]
        box_price = get_box_price_for(model)
        if box_price is None:
            continue
        max_boxes = total_qty // cap
        for n in range(1, max_boxes + 1):
            remain = total_qty - n * cap
            weight = calc_weight(remain)
            for idx, row in rows.iterrows():
                truck_cost = calc_truck_cost_from_row(weight, row)
                if truck_cost is None:
                    continue
                total_cost = n * box_price + truck_cost
                label = None
                for cand in ["流向类型","车型","重量类型","运输方式"]:
                    if cand in row.index and not pd.isna(row[cand]):
                        label = str(row[cand])
                        break
                if label is None:
                    label = f"方案-{idx}"
                plans.append({"方案类型":"混合","方式":f"{model}×{n} + {label}","箱子数":n,"车":label,"总费用":float(total_cost)})
    return plans

# -------------------------
# 计算并显示结果
# -------------------------
if st.button("计算最优方案"):
    all_plans = []
    all_plans += generate_box_plans()
    all_plans += generate_truck_plans()
    all_plans += generate_mix_plans()

    if not all_plans:
        st.error("未找到任何可用方案。可能原因：目标城市在 Excel 中缺失箱子或车价数据。页面下方显示已读取的表头和样本，请检查。")
    else:
        df = pd.DataFrame(all_plans)
        df = df.sort_values("总费用").reset_index(drop=True)
        st.success("计算完成，方案如下（已按总费用升序排序，最优置顶）")
        st.dataframe(df)
        st.subheader("🏆 最优方案")
        st.write(df.iloc[0])

# 在计算后，输出每个箱型的价格来源（市级/省级/无）
price_debug = {}
for m in box_models:
    p = get_box_price_for(m)
    price_debug[m] = p if p is not None else "无"
st.write("箱子单价（若为无表示该城市/省无数据）：", price_debug)

# 输出用于本次计算的整车价格行数与示例
st.write("匹配到的整车行数：", len(rows))
if len(rows) > 0:
    st.write("整车样例行（用于计费）：")
    st.write(rows.head(3))
