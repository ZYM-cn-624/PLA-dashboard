import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 页面基本配置
st.set_page_config(
    page_title="PLA Audience 广告分析看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 PLA Audience Performance 数据分析与优化建议看板")
st.markdown("上传您的 PLA Audience Performance 报表文件 (CSV/Excel)，系统将自动生成多维度数据看板与精准优化建议。")

# --- 侧边栏：文件上传与筛选器 ---
st.sidebar.header("📁 数据导入与筛选")
uploaded_file = st.sidebar.file_uploader("上传 PLA Performance 报表", type=["csv", "xlsx"])

@st.cache_data
def load_data(file):
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    
    # 清理列名空格
    df.columns = df.columns.str.strip()
    
    # 日期转换
    if 'Year Month Name' in df.columns and 'Week Day' in df.columns:
        df['Year Month Name'] = df['Year Month Name'].astype(str)
    if 'Bid Multiplier Change Date' in df.columns:
        df['Bid Multiplier Change Date'] = pd.to_datetime(df['Bid Multiplier Change Date'], errors='coerce')

    # 数值类型清洗（处理带逗号或百分号的字符串）
    numeric_cols = ['Impressions', 'Clicks', 'Spend', 'Click Through Rate (CTR)', 'OAM CPC', 'SPA Sales', 'SPA ROAS', 'Bid Multiplier']
    for col in numeric_cols:
        if col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace('%', '').str.replace(',', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 计算全局关键衍生指标（避免原始数据缺失或不准）
    df['Calculated_CTR'] = (df['Clicks'] / df['Impressions']).fillna(0)
    df['Calculated_CPC'] = (df['Spend'] / df['Clicks']).fillna(0)
    df['Calculated_ROAS'] = (df['SPA Sales'] / df['Spend']).fillna(0)
    
    return df

if uploaded_file is not None:
    try:
        df = load_data(uploaded_file)
        
        # 侧边栏多重筛选
        st.sidebar.subheader("🎯 维度筛选")
        selected_brand = st.sidebar.multiselect("Promoted Brand", options=df['Promoted Brand'].dropna().unique(), default=df['Promoted Brand'].dropna().unique())
        selected_audience = st.sidebar.multiselect("Audience Type", options=df['Audience Type'].dropna().unique(), default=df['Audience Type'].dropna().unique())
        
        # 应用筛选
        filtered_df = df[
            (df['Promoted Brand'].isin(selected_brand)) & 
            (df['Audience Type'].isin(selected_audience))
        ]

        # --- 核心 KPI 汇总卡片 ---
        st.subheader("📌 整体绩效概览 (KPI Summary)")
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        
        total_spend = filtered_df['Spend'].sum()
        total_sales = filtered_df['SPA Sales'].sum()
        total_clicks = filtered_df['Clicks'].sum()
        total_impressions = filtered_df['Impressions'].sum()
        
        overall_roas = total_sales / total_spend if total_spend > 0 else 0
        overall_ctr = total_clicks / total_impressions if total_impressions > 0 else 0
        overall_cpc = total_spend / total_clicks if total_clicks > 0 else 0

        kpi1.metric("总花费 (Spend)", f"${total_spend:,.2f}")
        kpi2.metric("总销售额 (SPA Sales)", f"${total_sales:,.2f}")
        kpi3.metric("整体 ROAS", f"{overall_roas:.2f}x")
        kpi4.metric("平均 CTR", f"{overall_ctr * 100:.2f}%")
        kpi5.metric("平均 CPC", f"${overall_cpc:.2f}")

        st.markdown("---")

        # --- 诊断与优化建议模块 ---
        st.subheader("💡 智能数据诊断与调优建议")
        
        # 定义目标 ROAS 阀值（允许用户动态调整）
        col_target, _ = st.columns([1, 2])
        target_roas = col_target.number_input("设置目标 ROAS (Target ROAS)", value=3.0, step=0.5)

        # 规则分类算法
        def diagnose_row(row):
            spend = row['Spend']
            roas = row['Calculated_ROAS']
            clicks = row['Clicks']
            ctr = row['Calculated_CTR']

            if spend > 50 and roas >= target_roas:
                return "🟢 高效放大：ROAS达标且有消费，建议提高 Bid Multiplier 争夺流量"
            elif spend > 50 and roas < (target_roas * 0.6):
                return "🔴 亏损预警：ROAS严重不达标，建议降低 Bid Multiplier 或暂停展示"
            elif spend > 30 and clicks > 20 and roas == 0:
                return "🟠 只耗不转化：有点击无转化，建议检查受众契合度或落地页"
            elif ctr < 0.003 and row['Impressions'] > 1000:
                return "🟡 吸引力不足：曝光高但 CTR 低，建议优化展示内容或检查匹配度"
            else:
                return "⚪ 观察期：数据量较小，建议继续观察"

        filtered_df['Diagnostic_Advice'] = filtered_df.apply(diagnose_row, axis=1)

        # 显示需要重点关注的建议汇总
        high_priority = filtered_df[filtered_df['Diagnostic_Advice'].str.startswith(('🔴', '🟢', '🟠'))]
        
        st.write(f"共检测到 **{len(high_priority)}** 项需要重点调整的组合：")
        st.dataframe(
            high_priority[[
                'Promoted Brand', 'Audience Type', 'Bid Multiplier', 
                'Spend', 'SPA Sales', 'Calculated_ROAS', 'Diagnostic_Advice'
            ]].sort_values(by='Spend', ascending=False),
            use_container_width=True
        )

        st.markdown("---")

        # --- 图表可视化模块 ---
        tab1, tab2, tab3 = st.tabs(["👥 Audience 受众分析", "🏷️ Brand 品牌分析", "⚙️ Bid Multiplier 竞价系数分析"])

        with tab1:
            st.write("### 不同 Audience Type 的 ROAS 与 Spend 分布")
            aud_summary = filtered_df.groupby('Audience Type').agg({
                'Spend': 'sum',
                'SPA Sales': 'sum',
                'Clicks': 'sum',
                'Impressions': 'sum'
            }).reset_index()
            aud_summary['ROAS'] = aud_summary['SPA Sales'] / aud_summary['Spend']
            
            fig_aud = px.bar(
                aud_summary, 
                x='Audience Type', 
                y='Spend', 
                color='ROAS',
                labels={'Spend': '总花费 ($)', 'ROAS': 'ROAS'},
                title="受众类型的消费与 ROAS 表现（颜色越深 ROAS 越高）",
                color_continuous_scale='Greens'
            )
            st.plotly_chart(fig_aud, use_container_width=True)

        with tab2:
            st.write("### 品牌 (Brand) 表现对比")
            brand_summary = filtered_df.groupby('Promoted Brand').agg({
                'Spend': 'sum',
                'SPA Sales': 'sum',
                'Clicks': 'sum'
            }).reset_index()
            brand_summary['ROAS'] = brand_summary['SPA Sales'] / brand_summary['Spend']

            fig_brand = px.scatter(
                brand_summary,
                x='Spend',
                y='SPA Sales',
                size='Clicks',
                color='Promoted Brand',
                hover_name='Promoted Brand',
                title="品牌 Spending vs Sales 散点图（气泡大小代表点击量）"
            )
            st.plotly_chart(fig_brand, use_container_width=True)

        with tab3:
            st.write("### 竞价系数 (Bid Multiplier) 对广告绩效的影响")
            fig_bid = px.box(
                filtered_df, 
                x='Bid Multiplier', 
                y='Calculated_ROAS',
                points="all",
                title="不同 Bid Multiplier 下的 ROAS 分布情况"
            )
            st.plotly_chart(fig_bid, use_container_width=True)

        # --- 原始数据透视表与导出 ---
        st.markdown("---")
        st.subheader("📋 明细数据查询与导出")
        st.dataframe(filtered_df, use_container_width=True)

    except Exception as e:
        st.error(f"解析文件时出错，请确认表头名称与格式正确。错误信息: {e}")

else:
    st.info("👈 请在左侧边栏上传您的 PLA Audience Performance CSV / Excel 文件以开始分析。")
