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
# 工具：规范化字符串（用于匹配省/市）
# -------------------------
def normalize(s):
    """规范化省市字符串：去首尾空格、小写、去除全角半角空格"""
    if pd.isna(s):
        return ""
    return str(s).strip().replace("　", "").replace(" ", "").lower()

# -------------------------
# 读取 Excel（缓存）
# -------------------------
@st.cache_data
def load_excels():
    # 请确保文件名与仓库里的文件一致
    truck_df = pd.read_excel("湖州始发精温车子价格.xlsx")
    box_df = pd.read_excel("湖州始发精温箱价格.xlsx")
    return truck_df, box_df

try:
    truck_df, box_df = load_excels()
except FileNotFoundError as e:
    st.error(
        "找不到 Excel 文件，请确保仓库根目录有：\n"
        "- 湖州始发精温车子价格.xlsx\n- 湖州始发精温箱价格.xlsx"
    )
    st.stop()

# -------------------------
# 列名查找函数（更宽容）
# -------------------------
def find_column(df, candidates):
    """从候选列名列表中返回第一个存在的列名，或者 None"""
    cols = df.columns.astype(str).tolist()
    for c in candidates:
        for col in cols:
            if col.strip().lower() == c.strip().lower():
                return col
            # 也允许候选词出现在列名中（例如 '到达省份' 与 '到达省'）
            if c.strip().lower() in col.strip().lower():
                return col
    return None

# 候选列表
to_prov_candidates = ["到达省","目的省","到省","province","到达省份","到省份"]
to_city_candidates = ["到达市","目的市","到市","city","到达城市","到城市"]
from_prov_candidates = ["始发省","出发省","始发省份","出发省份"]
from_city_candidates = ["始发市","出发市","始发城市","出发城市"]

to_prov_col = find_column(truck_df, to_prov_candidates)
to_city_col = find_column(truck_df, to_city_candidates)

if not to_prov_col or not to_city_col:
    st.error("在车价 Excel 中未找到目的省/市列（列名）。请检查表头，并确保包含到达省/到达市或类似字段。")
    st.write("Truck table columns:", truck_df.columns.tolist())
    st.stop()

# 生成省下拉与市下拉（从 truck_df 提取）
province_list = sorted(truck_df[to_prov_col].dropna().unique(), key=lambda x: str(x))
province = st.selectbox("选择目的省", province_list)

city_list = sorted(truck_df[truck_df[to_prov_col] == province][to_city_col].dropna().unique(), key=lambda x: str(x))
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
# 预处理：箱子表与车表的到达列
# -------------------------
box_cols = [c for c in box_df.columns.astype(str) if re.search(r'ev[\s\-_]?6|ev[\s\-_]?14|ev[\s\-_]?32|ev[\s\-_]?60|ev[\s\-_]?96|ev[\s\-_]?128', c, re.I)]
box_to_prov = find_column(box_df, to_prov_candidates)
box_to_city = find_column(box_df, to_city_candidates)

if not box_to_prov or not box_to_city:
    st.warning("箱子价格表未找到到达省/市列（会跳过箱子匹配）。")
    # 仍然允许继续，但箱子部分会返回 None

# -------------------------
# 在 truck_df 中识别“最低收费”与各重量区间列（保留原逻辑，但更健壮）
# -------------------------
cols = truck_df.columns.astype(str).tolist()
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

# 重量区间映射（尝试把常见区间抓出来）
bands = [("1-20", (1,20)), ("20-50", (20,50)), ("50-100", (50,100)), ("100-500", (100,500)), (">500", (500, None))]
band_col_map = {}
for col in cols:
    col_norm = col.lower().replace(" ", "").replace("kg","")
    for key, rng in bands:
        patterns = [
            key.replace("-", ""),
            key.replace("-", "_"),
            key,
            key.replace("-", "–"),
            key.replace("-", "—"),
            key.replace("-", "to"),
        ]
        for p in patterns:
            if p in col_norm:
                band_col_map[key] = col
                break

# -------------------------
# 计算重量
# -------------------------
def calc_weight(qty):
    # 原逻辑：每 100 盒 = 3.6 吨  => weight = qty/100*3.6（单位：吨）
    return qty / 100.0 * 3.6

# -------------------------
# 获取箱子价格（市级优先、省级备选）
# -------------------------
def get_box_price_for(model, province_value, city_value):
    """返回 float 价格或 None"""
    if not box_cols or not box_to_prov or not box_to_city:
        return None

    # 规范化输入
    norm_prov = normalize(province_value)
    norm_city = normalize(city_value)

    def extract_price_from_row(row):
        for col in box_cols:
            col_norm = re.sub(r'\s+', '', str(col)).lower()
            model_norm = model.replace("-", "").lower()
            if model_norm in col_norm:
                try:
                    v = row[col]
                    if pd.isna(v):
                        return None
                    return float(v)
                except Exception:
                    return None
        return None

    # 市级匹配（使用 normalize 比较）
    for idx, r in box_df.iterrows():
        if normalize(r[box_to_prov]) == norm_prov and normalize(r[box_to_city]) == norm_city:
            v = extract_price_from_row(r)
            if v is not None:
                return v

    # 省级匹配（市为空或没有市匹配）
    for idx, r in box_df.iterrows():
        if normalize(r[box_to_prov]) == norm_prov:
            v = extract_price_from_row(r)
            if v is not None:
                return v

    return None

# -------------------------
# 计算车费（单行）
# -------------------------
def calc_truck_cost_from_row(weight, row):
    # 读取最低收费
    low = None
    if min_fee_col and min_fee_col in row.index:
        try:
            low = float(row[min_fee_col])
        except:
            low = None

    # 根据 weight 选择 band_key
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

    unit = None
    if band_key in band_col_map:
        colname = band_col_map[band_key]
        try:
            unit = float(row[colname])
        except:
            unit = None

    # 退化匹配：检查列名里是否包含带区间的关键词
    if unit is None:
        for col in row.index:
            name = str(col).lower().replace(" ", "")
            if band_key.replace("-", "") in name:
                try:
                    unit = float(row[col])
                    break
                except:
                    pass

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
# 在选择后，预先计算匹配到的truck行（供显示与生成方案使用）
# -------------------------
rows_matched = truck_df[(truck_df[to_prov_col].apply(lambda x: normalize(x)) == normalize(province)) &
                        (truck_df[to_city_col].apply(lambda x: normalize(x)) == normalize(city))]

# -------------------------
# 生成方案函数（使用外层 rows_matched）
# -------------------------
def generate_box_plans():
    plans = []
    for model in box_models:
        cap = capacity_table[model][type_key]
        price = get_box_price_for(model, province, city)
        if price is None:
            continue
        need = math.ceil(total_qty / cap)
        cost = need * price
        plans.append({"方案类型":"箱子","方式":model,"箱子数":need,"车":"无","总费用":cost})
    return plans

def generate_truck_plans():
    plans = []
    weight = calc_weight(total_qty)
    rows = rows_matched
    if rows.empty:
        return plans
    for idx, row in rows.iterrows():
        cost = calc_truck_cost_from_row(weight, row)
        if cost is None:
            continue
        # 生成标签：优先找流向类型/车型等列
        label = None
        for cand in ["流向类型","车型","重量类型","运输方式"]:
            if cand in row.index and not pd.isna(row[cand]):
                label = str(row[cand])
                break
        if label is None:
            label = f"方案-{idx}"
        plans.append({"方案类型":"整车","方式":label,"箱子数":0,"车":label,"总费用":float(cost)})
    return plans

def generate_mix_plans():
   plans = []
if rows_matched.empty or box_df is None:
   return plans

# 先生成所有可能的箱型组合（为了性能，组合数限制在合理范围，例如 1~3 种箱型组合）
# 这里使用简单策略：最多组合 2~3 种箱型
   for r in range(1, 3+1):
      for box_combo in itertools.combinations_with_replacement(box_models, r):
        # 生成每种箱型可能数量
        max_counts = [math.ceil(total_qty / capacity_table[b][type_key]) for b in box_combo]
        # 枚举数量（1~max_count）
        ranges = [range(1, mc+1) for mc in max_counts]
        for counts in itertools.product(*ranges):
            total_boxed = sum([counts[i]*capacity_table[box_combo[i]][type_key] for i in range(len(box_combo))])
            if total_boxed > total_qty:
                continue
            remain = total_qty - total_boxed
            weight_remain = calc_weight(remain)
            for idx, row in rows_matched.iterrows():
                truck_cost = calc_truck_cost_from_row(weight_remain, row)
                if truck_cost is None:
                    continue
                # 箱子总费用
                box_cost = sum([get_box_price_for(box_combo[i], province, city) * counts[i] for i in range(len(box_combo))])
                total_cost = box_cost + truck_cost
                label_boxes = " + ".join([f"{box_combo[i]}×{counts[i]}" for i in range(len(box_combo))])
                truck_label = None
                for cand in ["流向类型","车型","重量类型","运输方式"]:
                    if cand in row.index and not pd.isna(row[cand]):
                        truck_label = str(row[cand])
                        break
                if truck_label is None:
                    truck_label = f"方案-{idx}"
                plans.append({
                    "方案类型":"混合",
                    "方式":f"{label_boxes} + 剩余用车({truck_label})",
                    "箱子数":total_boxed,
                    "车":truck_label,
                    "总费用":total_cost
                })
   return plans

# -------------------------
# 计算并显示结果（按钮触发）
# -------------------------
if st.button("计算最优方案"):
all_plans = []
all_plans += generate_box_plans() # 纯箱子方案
all_plans += generate_truck_plans() # 纯整车方案
all_plans += generate_mix_plans_advanced() # 增强混合方案

if not all_plans:
    st.error("未找到任何可用方案，可能目标城市在 Excel 中缺失数据")
else:
    df = pd.DataFrame(all_plans)
    df = df.sort_values("总费用").reset_index(drop=True)
    st.success("计算完成，方案如下（已按总费用升序排序，最优置顶）")
    st.dataframe(df)
    st.subheader("🏆 最优方案")
    st.write(df.iloc[0])

# -------------------------
# 计算后调试输出：箱子单价来源与匹配到的整车行数
# -------------------------
price_debug = {}
for m in box_models:
    p = get_box_price_for(m, province, city)
    price_debug[m] = p if p is not None else "无"
st.write("箱子单价（若为无表示该城市/省无数据）：", price_debug)

st.write("匹配到的整车行数：", len(rows_matched))
if len(rows_matched) > 0:
    st.write("整车样例行（用于计费）：")
    st.write(rows_matched.head(3))

# 额外：显示读取到的表头，便于调试列名问题
with st.expander("查看读取到的表头（调试用）"):
    st.write("车价表列头：", truck_df.columns.tolist())
    st.write("箱子表列头：", box_df.columns.tolist())
