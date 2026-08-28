import streamlit as st
import pandas as pd
import plotly.express as px

# 页面配置
st.set_page_config(
    page_title="PLA Audience 广告分析看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 PLA Audience Performance 智能数据分析与预警看板")
st.markdown("自动解析 Home Depot PLA Performance 报表，监控 **CPC 偏高** 与 **Spend 花费风险**，输出优化建议。")

@st.cache_data
def load_data(file):
    # 自动定位标题行（兼容顶部有元数据/Notice的Excel报表）
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

    # 格式化表头
    df.columns = df.columns.astype(str).str.strip()

    # 处理 Audience Type 缺失值
    if 'Audience Type' in df.columns:
        df['Audience Type'] = df['Audience Type'].fillna('All Customers (Non-Pro)').astype(str)

    # 清理并转换数值列
    numeric_cols = [
        'Impressions', 'Clicks', 'Spend', 'Click Through Rate (CTR)', 
        'OAM CPC', 'SPA Sales', 'SPA ROAS', 'Bid Multiplier'
    ]
    for col in numeric_cols:
        if col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace('%', '').str.replace('$', '').str.replace(',', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 派生关键计算列
    df['Calculated_CTR'] = df.apply(lambda r: r['Clicks'] / r['Impressions'] if r['Impressions'] > 0 else 0, axis=1)
    df['Calculated_CPC'] = df.apply(lambda r: r['Spend'] / r['Clicks'] if r['Clicks'] > 0 else 0, axis=1)
    df['Calculated_ROAS'] = df.apply(lambda r: r['SPA Sales'] / r['Spend'] if r['Spend'] > 0 else 0, axis=1)

    return df

# --- 侧边栏：文件上传与预警阈值设置 ---
st.sidebar.header("📁 文件上传")
uploaded_file = st.sidebar.file_uploader("上传 PLA Performance 报表 (xlsx/csv)", type=["xlsx", "csv"])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 预警阈值设置")
max_cpc_threshold = st.sidebar.number_input("最高容忍 CPC 阈值 ($)", value=2.50, step=0.10, help="CPC 超过此设定值将触发高 CPC 提醒")
high_spend_threshold = st.sidebar.number_input("高 Spend 监控线 ($)", value=30.00, step=5.00, help="花费超过此门槛将重点检测转化效果")
target_roas = st.sidebar.number_input("目标 ROAS (Target ROAS)", value=3.00, step=0.50)

if uploaded_file is not None:
    try:
        df = load_data(uploaded_file)
        
        # 侧边栏筛选
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 维度筛选")
        
        months = sorted(df['Month Name'].dropna().unique().tolist()) if 'Month Name' in df.columns else []
        selected_months = st.sidebar.multiselect("月份筛选", options=months, default=months) if months else []
        
        brands = sorted(df['Promoted Reporting Brand'].dropna().unique().tolist()) if 'Promoted Reporting Brand' in df.columns else []
        selected_brands = st.sidebar.multiselect("品牌筛选", options=brands, default=brands) if brands else []
        
        audiences = sorted(df['Audience Type'].dropna().unique().tolist())
        selected_audiences = st.sidebar.multiselect("客群类型筛选", options=audiences, default=audiences)

        # 数据过滤
        filtered_df = df.copy()
        if selected_months and 'Month Name' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Month Name'].isin(selected_months)]
        if selected_brands and 'Promoted Reporting Brand' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Promoted Reporting Brand'].isin(selected_brands)]
        filtered_df = filtered_df[filtered_df['Audience Type'].isin(selected_audiences)]

        # --- 核心诊断逻辑 ---
        def diagnose_row(row):
            spend = row['Spend']
            cpc = row['Calculated_CPC']
            roas = row['Calculated_ROAS']
            sales = row['SPA Sales']
            clicks = row['Clicks']

            alerts = []
            if cpc > max_cpc_threshold and spend >= 10:
                alerts.append(f"⚠️ CPC偏高 (${cpc:.2f})")
            if spend >= high_spend_threshold and sales == 0:
                alerts.append(f"💸 高消费零转化 (${spend:.2f})")
            elif spend >= high_spend_threshold and roas < (target_roas * 0.5):
                alerts.append(f"🔴 高消费低ROAS ({roas:.2f}x)")

            if alerts:
                return " | ".join(alerts)
            elif spend >= 30 and roas >= target_roas:
                return "🟢 高效放大：可调高 Bid Multiplier"
            elif spend == 0:
                return "⚪ 未消耗"
            else:
                return "🔵 表现平稳 / 观察期"

        filtered_df['Diagnostic_Advice'] = filtered_df.apply(diagnose_row, axis=1)

        # 预警汇总统计
        high_cpc_count = len(filtered_df[filtered_df['Diagnostic_Advice'].str.contains('CPC偏高', na=False)])
        waste_spend_count = len(filtered_df[filtered_df['Diagnostic_Advice'].str.contains('高消费', na=False)])

        # --- 顶部 KPI 概览卡片 ---
        st.subheader("📌 广告整体绩效概览")
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        
        tot_spend = filtered_df['Spend'].sum()
        tot_sales = filtered_df['SPA Sales'].sum()
        tot_clicks = filtered_df['Clicks'].sum()
        tot_impressions = filtered_df['Impressions'].sum()
        
        avg_roas = tot_sales / tot_spend if tot_spend > 0 else 0
        avg_cpc = tot_spend / tot_clicks if tot_clicks > 0 else 0

        kpi1.metric("总花费 (Spend)", f"${tot_spend:,.2f}")
        kpi2.metric("总销售额 (Sales)", f"${tot_sales:,.2f}")
        kpi3.metric("整体 ROAS", f"{avg_roas:.2f}x")
        kpi4.metric("平均 CPC", f"${avg_cpc:.2f}", delta=f"{avg_cpc - max_cpc_threshold:+.2f} vs 阈值", delta_color="inverse")
        kpi5.metric("风险预警数", f"{high_cpc_count + waste_spend_count} 项", delta=f"CPC高: {high_cpc_count} | 消费高: {waste_spend_count}", delta_color="off")

        st.markdown("---")

        # --- 重点预警模块 (CPC 与 Spend 提醒) ---
        st.subheader("🚨 重点预警与调优建议")
        
        # 筛选需要关注的预警项
        alert_df = filtered_df[filtered_df['Diagnostic_Advice'].str.contains('⚠️|💸|🔴', na=False)].sort_values(by='Spend', ascending=False)

        if not alert_df.empty:
            st.warning(f"检测到 **{len(alert_df)}** 条广告组合需要重点介入调整：")
            
            show_cols = [
                'Month Name', 'Promoted OMSID Number', 'Promoted OMSID Description', 
                'Audience Type', 'Bid Multiplier', 'Spend', 'Calculated_CPC', 
                'SPA Sales', 'Calculated_ROAS', 'Diagnostic_Advice'
            ]
            # 过滤只展示存在于数据表中的列
            existing_cols = [c for c in show_cols if c in alert_df.columns]
            
            st.dataframe(
                alert_df[existing_cols].style.format({
                    'Spend': '${:,.2f}',
                    'Calculated_CPC': '${:,.2f}',
                    'SPA Sales': '${:,.2f}',
                    'Calculated_ROAS': '{:.2f}x'
                }),
                use_container_width=True
            )
        else:
            st.success("🎉 当前筛选条件下未发现 CPC 异常偏高或高花费低转化的预警项！")

        st.markdown("---")

        # --- 图表分析模块 ---
        tab1, tab2, tab3 = st.tabs(["💰 Spend vs. CPC 散点诊断", "👥 Audience 客群分析", "📦 SKU/OMSID 消费排行"])

        with tab1:
            st.write("### Spend 与 CPC 关系分布图（右上象限为高风险高花费区）")
            fig_scatter = px.scatter(
                filtered_df,
                x='Spend',
                y='Calculated_CPC',
                size='Clicks',
                color='Diagnostic_Advice',
                hover_data=['Promoted OMSID Number', 'Audience Type', 'SPA Sales'],
                labels={'Spend': '总花费 ($)', 'Calculated_CPC': 'CPC 单次点击成本 ($)'},
                title="Spend vs. CPC 风险矩阵图"
            )
            # 添加预警参考线
            fig_scatter.add_hline(y=max_cpc_threshold, line_dash="dash", line_color="red", annotation_text=f"CPC 阈值 (${max_cpc_threshold:.2f})")
            fig_scatter.add_vline(x=high_spend_threshold, line_dash="dash", line_color="orange", annotation_text=f"Spend 预警线 (${high_spend_threshold:.2f})")
            st.plotly_chart(fig_scatter, use_container_width=True)

        with tab2:
            st.write("### 各 Audience Type 消费与 CPC 表现")
            aud_summary = filtered_df.groupby('Audience Type').agg({
                'Spend': 'sum',
                'Clicks': 'sum',
                'SPA Sales': 'sum'
            }).reset_index()
            aud_summary['CPC'] = aud_summary.apply(lambda r: r['Spend'] / r['Clicks'] if r['Clicks'] > 0 else 0, axis=1)
            aud_summary['ROAS'] = aud_summary.apply(lambda r: r['SPA Sales'] / r['Spend'] if r['Spend'] > 0 else 0, axis=1)

            fig_aud = px.bar(
                aud_summary,
                x='Audience Type',
                y='Spend',
                color='CPC',
                text_auto='.2f',
                labels={'Spend': '总花费 ($)', 'CPC': '平均 CPC ($)'},
                title="受众类型 Spend 分布（柱体颜色表示 CPC 高低）",
                color_continuous_scale='Reds'
            )
            st.plotly_chart(fig_aud, use_container_width=True)

        with tab3:
            st.write("### Spend 排名前 10 的 SKU/OMSID 表现")
            if 'Promoted OMSID Number' in filtered_df.columns:
                sku_summary = filtered_df.groupby(['Promoted OMSID Number', 'Promoted OMSID Description']).agg({
                    'Spend': 'sum',
                    'Clicks': 'sum',
                    'SPA Sales': 'sum'
                }).reset_index().sort_values(by='Spend', ascending=False).head(10)
                
                sku_summary['CPC'] = sku_summary.apply(lambda r: r['Spend'] / r['Clicks'] if r['Clicks'] > 0 else 0, axis=1)
                sku_summary['ROAS'] = sku_summary.apply(lambda r: r['SPA Sales'] / r['Spend'] if r['Spend'] > 0 else 0, axis=1)

                st.dataframe(
                    sku_summary.style.format({
                        'Spend': '${:,.2f}',
                        'CPC': '${:,.2f}',
                        'SPA Sales': '${:,.2f}',
                        'ROAS': '{:.2f}x'
                    }),
                    use_container_width=True
                )

        # --- 全量明细数据 ---
        st.markdown("---")
        st.subheader("📋 筛选后的数据明细")
        st.dataframe(filtered_df, use_container_width=True)

    except Exception as e:
        st.error(f"❌ 解析数据时出错：{e}")

else:
    st.info("👈 请在左侧边栏上传您的 PLA Audience Performance Excel / CSV 报表以开启分析与提醒。")
