import streamlit as st
import pandas as pd
import altair as alt

from config import COMPANY_CONFIGS
from reporting import render_revenue_table
from revenue_service import (
    get_company_revenue,
    select_recent_revenue,
)


st.set_page_config(
    page_title="FinSight AI",
    layout="wide",
)

st.title("FinSight AI")
st.caption("基于 SEC 申报数据的年度营业收入研究")

ticker = st.selectbox(
    "选择公司",
    options=list(COMPANY_CONFIGS),
)

years = st.slider(
    "查看最近几个完整财年",
    min_value=1,
    max_value=10,
    value=3,
)

if "revenue_report" not in st.session_state:
    st.session_state["revenue_report"] = None

if st.button("查询收入", type="primary"):
    try:
        with st.spinner("正在获取和处理财务数据……"):
            report = select_recent_revenue(
                get_company_revenue(ticker),
                years,
            )

        # 只有查询成功才替换已有结果
        st.session_state["revenue_report"] = report

    except Exception:
        st.error(
            "查询失败，请检查 SEC_USER_AGENT 和网络连接。"
            "如有上次成功结果，将继续展示。"
        )
        import traceback
        traceback.print_exc()

# 展示逻辑放在按钮判断外，重新执行脚本时仍能显示
report = st.session_state["revenue_report"]

if report is not None:
    if (
        report["ticker"] != ticker
        or report["requested_years"] != years
    ):
        st.info(
            f"当前展示的是上次查询结果："
            f"{report['ticker']}，"
            f"请求 {report['requested_years']} 个财年。"
            "点击“查询收入”更新。"
        )

    st.subheader(report["company_name"])
    st.markdown(render_revenue_table(report))
    chart_df = pd.DataFrame(report["annual_revenue"])
    chart_df = chart_df.sort_values("fiscal_year")

    # 转成字符串，让横轴按财年分类，避免出现小数年份
    chart_df["财年"] = chart_df["fiscal_year"].astype(str)
    chart_df["营业收入（亿美元）"] = (
        chart_df["revenue"] / 100_000_000
    )

    st.subheader("年度营业收入趋势")
    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X(
                "财年:O",
                sort="ascending",
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y(
                "营业收入（亿美元）:Q",
                scale=alt.Scale(zero=True),
            ),
            tooltip=[
                alt.Tooltip("财年:O"),
                alt.Tooltip(
                    "营业收入（亿美元）:Q",
                    format=",.2f",
                ),
            ],
        )
    )

    st.altair_chart(chart, use_container_width=True)