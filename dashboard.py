import streamlit as st
import pandas as pd
import altair as alt
import asyncio

from research_agent import (
    run_research,
    format_research_result,
)

from reporting import (
    render_revenue_table,
    render_profitability_table,
)

from config import COMPANY_CONFIGS

from revenue_service import (
    get_company_revenue,
    get_company_profitability,
    select_recent_revenue,
)


st.set_page_config(
    page_title="FinSight AI",
    layout="wide",
)

st.title("FinSight AI")
st.caption("基于 SEC 申报数据的收入增长与盈利能力研究")

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

if "profitability_report" not in st.session_state:
    st.session_state["profitability_report"] = None

if st.button("查询财务数据", type="primary"):
    try:
        with st.spinner("正在获取和处理财务数据……"):
            report = select_recent_revenue(
                get_company_revenue(ticker),
                years,
            )

            profitability = get_company_profitability(ticker)

            # 与收入表展示相同的财年
            selected_years = set(report["selected_fiscal_years"])

            profitability["annual_profitability"] = [
                row
                for row in profitability["annual_profitability"]
                if row["fiscal_year"] in selected_years
            ]

        # 两份结果都准备成功后，再一起更新页面状态
        st.session_state["revenue_report"] = report
        st.session_state["profitability_report"] = profitability

    except Exception:
        st.error(
            "查询失败，请检查 SEC_USER_AGENT 和网络连接。"
            "如有上次成功结果，将继续展示。"
        )
        import traceback
        traceback.print_exc()

# 每次页面重新执行，都读取上次成功的查询结果。
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
            "点击“查询财务数据”更新。"
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
    profitability = st.session_state["profitability_report"]

    if profitability is not None:
        st.markdown(
            render_profitability_table(profitability)
        )
    else:
        st.info("请重新查询，以加载盈利能力数据。")


st.divider()
st.header("Agent 自然语言查询")
st.caption(
    "支持 MSFT、AAPL 的年度营收、收入同比、归母净利润和净利率查询。"
    "提交会调用 OpenAI API 并产生费用；普通财务查询不调用模型。"
)

if "agent_response" not in st.session_state:
    st.session_state["agent_response"] = None

with st.form("research_question_form"):
    question = st.text_input(
        "研究问题",
        placeholder="例如：查询苹果最近三个完整财年的收入和同比。",
    )
    submitted = st.form_submit_button("提交给 Agent")

if submitted:
    if not question.strip():
        st.warning("请输入研究问题。")
    else:
        try:
            with st.spinner("Agent 正在查询……"):
                result = asyncio.run(
                    run_research(question)
                )

            st.session_state["agent_response"] = {
                "question": question.strip(),
                "answer": format_research_result(result),
            }

        except Exception:
            st.error(
                "Agent 查询失败，请查看终端错误详情。"
                "上次成功结果将保留。"
            )
            import traceback
            traceback.print_exc()

response = st.session_state["agent_response"]

if response is not None:
    st.subheader("上次成功的 Agent 查询")
    st.caption(f"问题：{response['question']}")
    st.markdown(response["answer"])
