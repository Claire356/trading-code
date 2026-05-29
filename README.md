# Three-Market Long-Only Trading Agent

这是把原来的多市场做多策略改成 Python agent 后的版本。它不是 TradingView 脚本，而是一个可审计、可扩展的交易代理骨架：CSV 数据输入、策略信号、风控仓位、纸交易撮合、回测统计都已经分层。

## 能做什么

- 支持 `US`、`A_SHARES`、`HK` 三个市场配置。
- 只做多，不生成做空订单。
- 使用趋势过滤、指数/基准过滤、相对强弱过滤、突破/回调/布林回收三类入场。
- 使用 ATR 初始止损、盈亏比止盈、保本止损、ATR 移动止损、时间止损和每日亏损锁。
- A股支持近似 T+1、涨停附近不追买、整数手。
- 港股支持 lot size 配置。
- 美股、A股、港股分别有常规交易时段过滤。
- 账户用 USD，A股/港股通过 `usd_to_symbol_fx` 转换成本地币做仓位计算。

## CSV 格式

CSV 至少包含这些列：

```csv
timestamp,open,high,low,close,volume
2024-01-02,100.00,101.00,99.50,100.80,1000000
```

`timestamp` 支持 ISO 格式，例如 `2025-01-02T10:00:00-05:00`。日线数据用日期即可。

## 快速运行

生成一份示例数据：

```bash
python3 scripts/generate_sample_data.py
```

打开本地界面：

```bash
python3 scripts/start_ui.py
```

然后在浏览器访问：

```text
http://127.0.0.1:8765
```

在 VS Code 窗口里打开界面：

1. 打开命令面板：`Cmd+Shift+P`
2. 选择 `Tasks: Run Task`
3. 选择 `Start Trading Agent UI`
4. 再打开命令面板，选择 `Simple Browser: Show`
5. 输入 `http://127.0.0.1:8765`

部署到 Vercel：

```bash
vercel --prod
```

Vercel 部署后需要在项目环境变量里配置 `ANTHROPIC_API_KEY` 和 `MIROMIND_API_KEY`。云端 demo 使用 serverless `/tmp` 保存纸交易状态，适合演示界面和报告，不适合作为长期真实交易状态存储。

运行回测：

```bash
python3 -m trading_agent.cli backtest --config configs/us_sample.json
```

查看最新一根 K 线的信号：

```bash
python3 -m trading_agent.cli signal --config configs/us_sample.json
```

运行一次持久化纸交易 agent：

```bash
python3 -m trading_agent.cli run-once --config configs/us_sample.json --state .agent_state/us.json
```

也可以直接运行已经生成好的 demo agent：

```bash
python3 scripts/run_agent.py
```

重置这个 demo agent 的纸交易状态：

```bash
python3 scripts/run_agent.py --reset
```

再次运行同一根 K 线时，agent 会返回 `bar_already_processed`，避免重复下单。需要重新开始纸交易状态时：

```bash
python3 -m trading_agent.cli reset-state --config configs/us_sample.json --state .agent_state/us.json
```

导出交易记录：

```bash
python3 -m trading_agent.cli backtest --config configs/us_sample.json --trades-out trades.csv
```

生成配置模板：

```bash
python3 -m trading_agent.cli sample-config --market US
python3 -m trading_agent.cli sample-config --market A_SHARES
python3 -m trading_agent.cli sample-config --market HK
```

## 接入 Claude 和 Miromind

先设置环境变量，不要把真实 key 写进代码：

```bash
export ANTHROPIC_API_KEY="你的 Claude API Key"
export MIROMIND_API_KEY="你的 Miromind API Key"
```

也可以复制 `.env.example` 为 `.env`，`scripts/run_agent.py` 和 `scripts/check_llm_connections.py` 会自动读取项目根目录的 `.env`。

检查 API 是否连通：

```bash
python3 scripts/check_llm_connections.py --provider both
```

让 demo agent 在处理最新 K 线后生成报告。默认是快速报告，只调用 Claude 做低成本风险复核：

```bash
python3 scripts/run_agent.py --with-research
```

报告分三档：

```bash
python3 scripts/run_agent.py --with-research --report-tier quick
python3 scripts/run_agent.py --with-research --report-tier medium --research-provider both
MIROMIND_TIMEOUT_SECONDS=120 python3 scripts/run_agent.py --with-research --report-tier deep --research-provider both
```

三档含义：

- `quick`：快速报告，默认只做 Claude 风险复核，不调用 Miromind。
- `medium`：中度报告，Claude 风险复核 + Miromind chat 简版研究。
- `deep`：深度报告，Claude 风险复核 + Miromind Responses/更长研究；适合重大交易前，不建议每次都跑。

也可以指定 provider：

```bash
python3 scripts/run_agent.py --with-research --research-provider claude
python3 scripts/run_agent.py --with-research --research-provider miromind
```

报告会把“规则信号”“研究结论”“执行姿态”分开。`execution_posture` 只给运行层建议，例如 `observe`、`paper_or_human_review_before_real_order`，不代表自动实盘下单，也不是投资建议。

默认模型可以用环境变量覆盖：

```bash
export CLAUDE_MODEL="claude-sonnet-4-20250514"
export MIROMIND_MODEL="mirothinker-1-7-deepresearch-mini"
```

如果 Miromind DeepResearch 同步调用较慢，可以调短或调长超时：

```bash
export MIROMIND_TIMEOUT_SECONDS=45
export MIROMIND_RESEARCH_MODE=chat
```

需要强制使用 Miromind Responses API 时：

```bash
export MIROMIND_RESEARCH_MODE=responses
```

## 实盘接入方式

当前版本故意只内置 `PaperBroker`。真实下单应新增一个 broker adapter，实现同样的买入/卖出接口，再接入你的券商 API。这样做的原因很简单：策略、风控、执行解耦后，接 IBKR、富途、老虎、QMT、掘金等都不需要重写策略核心。

实盘前必须补齐：

- 实时行情源和历史行情源。
- 真实手续费、印花税、平台费、交易征费。
- 订单状态回报、撤单、部分成交处理。
- 断线重连和重复下单保护。
- 持仓同步，不能只相信本地状态。
- 每个市场的节假日、半日市、停牌、涨跌停、融资融券限制。

## 重要提示

这不是投资建议，也不是可以直接接资金裸跑的黑箱。先用历史数据和纸交易跑足够长时间，确认数据质量、交易成本、滑点和券商接口都可靠后，再考虑小资金验证。
