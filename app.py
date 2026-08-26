import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="PLA Audience 广告分析看板", layout="wide")
st.title("📊 PLA Audience Performance 数据分析看板")

@st.cache_data
def load_data(file):
    # 1. 自动寻找真正表头所在的位置（跳过顶部的 Notice 和时间说明）
    df_raw = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
    
    header_row_idx = None
    for idx, row in df_raw.iterrows():
        row_str = " ".join(row.dropna().astype(str))
        if 'Promoted Reporting Brand' in row_str or 'Audience Type' in row_str or 'Spend' in row_str:
            header_row_idx = idx
            break
            
    if file.name.endswith('.xlsx'):
        df = pd.read_excel(file, skiprows=header_row_idx + 1 if header_row_idx is not None else 0)
    else:
        df = pd.read_csv(file, skiprows=header_row_idx + 1 if header_row_idx is not None else 0)

    # 2. 清理表头空格
    df.columns = df.columns.astype(str).str.strip()

    # 3. 处理 Audience Type 空值（将 NaN 补充为 'All Customers / Non-Pro'）
    if 'Audience Type' in df.columns:
        df['Audience Type'] = df['Audience Type'].fillna('All Customers / Non-Pro').astype(str)

    # 4. 数值列清洗与空值填充
    numeric_cols = ['Impressions', 'Clicks', 'Spend', 'Click Through Rate (CTR)', 'OAM CPC', 'SPA Sales', 'SPA ROAS', 'Bid Multiplier']
    for col in numeric_cols:
        if col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace('%', '').str.replace('$', '').str.replace(',', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 5. 计算派生指标
    df['Calculated_ROAS'] = df.apply(lambda r: r['SPA Sales'] / r['Spend'] if r['Spend'] > 0 else 0, axis=1)
    df['Calculated_CTR'] = df.apply(lambda r: r['Clicks'] / r['Impressions'] if r['Impressions'] > 0 else 0, axis=1)

    return df

uploaded_file = st.sidebar.file_uploader("上传您的 PLA Excel 报表", type=["xlsx", "csv"])

if uploaded_file:
    df = load_data(uploaded_file)
    st.success(f"成功导入 {len(df)} 条广告表现数据！")
    
    # 核心指标显示
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总广告花费", f"${df['Spend'].sum():,.2f}")
    col2.metric("总广告销售额", f"${df['SPA Sales'].sum():,.2f}")
    overall_roas = df['SPA Sales'].sum() / df['Spend'].sum() if df['Spend'].sum() > 0 else 0
    col3.metric("整体 ROAS", f"{overall_roas:.2f}x")
    col4.metric("总点击数", f"{df['Clicks'].sum():,.0f}")
    
    st.dataframe(df, use_container_width=True)
