# FinSight AI

Financial Research & Investment Intelligence System.

目前实现了基于 SEC Company Facts API 的年度营业收入提取、
同比增长率计算及来源追溯。Agent 功能尚未接入。

## 当前功能

- 支持 Microsoft（MSFT）和 Apple（AAPL）
- 筛选常规完整财年，包括 52/53 周财年
- 同一会计期间保留最新披露记录
- 计算连续财年的营业收入同比增长率
- 导出包含申报编号和来源链接的 CSV
- 使用 pytest 进行离线测试

## 安装

以下命令适用于 Windows CMD：

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## 配置

使用自己的真实联系邮箱设置 SEC User-Agent：

```cmd
set "SEC_USER_AGENT=FinSight-AI your-email@domain.com"
```

该设置仅对当前终端会话有效。

## 运行

```cmd
python main.py --ticker MSFT
python main.py --ticker AAPL
```

默认公司为 MSFT。
结果保存至 `data/`，包含 CSV 表格和结构化 JSON 文件。

## 测试

```cmd
python -m pytest -q
```

测试使用手写数据，不访问 SEC。

## 当前限制

- 仅配置并运行验证了 MSFT、AAPL
- 使用指定收入标签，不自动合并历史标签
- 按最新披露口径处理历史数据，不适用于直接进行时点回测
- 同比未调整 52/53 周财年的周数差异
- 来源链接指向申报目录，尚未定位到具体表格
- 已人工核对 MSFT 部分年份，AAPL 尚待核对

## 初步 Agent 评估

单轮运行 4 个用例，工具路由检查通过 4/4。
人工核对发现财务年份、数字和来源链接与工具输出一致，
但一条回答存在单位表述矛盾。

本轮共使用 3,111 tokens，平均端到端耗时约 3.53 秒。
结果仅代表本次小样本评估，不代表总体准确率。

## SEC 数据缓存

Company Facts 原始数据缓存在 `data/cache/`，有效期为一小时。
缓存过期或损坏时重新获取，不自动回退使用过期数据。

强制刷新：

```cmd
python main.py --ticker MSFT --refresh
```cmd

## 数据来源

[SEC Company Facts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)