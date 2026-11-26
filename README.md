# FlowPilot V1.0

面向小企业售后服务场景的 AI Agent 系统。当前仓库处于 **Milestone 2**：
在 Milestone 1 的订单查询能力之上，加入了**确定性的售后政策与退款资格判断**。

> 本项目目前**不执行真实退款**，也**不允许 AI 绕过人工审批**。
> 所有 `eligible` 结果只表示“可以进入人工审批”，不代表退款已获批准。

## 当前进度

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| FastAPI 后端 | ✅ 已完成 | `backend/main.py` |
| SQLite 订单库 | ✅ 已完成 | `data/flowpilot.db`，启动时自动建表/迁移 |
| 订单查询 API | ✅ 已完成 | `GET /orders/{order_id}`，不存在返回 404 |
| 售后政策文档 | ✅ 已完成 | `policies/refund_policy.md`（演示政策 v1.0） |
| 交付日期字段 | ✅ 已完成 | `orders.delivered_at`，可空，旧库自动升级 |
| 退款资格规则 | ✅ 已完成 | `backend/refund_rules.py`，纯函数、可注入日期 |
| 资格查询 API | ✅ 已完成 | `GET /orders/{order_id}/refund-eligibility`，只读 |
| 自动化测试 | ✅ 已完成 | 53 项，使用临时数据库 |
| LLM / RAG | ❌ 未实现 | 后续里程碑 |
| 人工审批工作流 | ❌ 未实现 | 后续里程碑 |
| 售后工单 | ❌ 未实现 | 后续里程碑 |
| 审计日志 | ❌ 未实现 | 后续里程碑 |
| React 前端 | ❌ 未实现 | 后续里程碑 |

## 目录结构

```text
flowpilot/
├── backend/
│   ├── main.py            # FastAPI 应用与 HTTP 路由
│   ├── database.py        # SQLite 连接、建表、增量迁移、订单查询
│   └── refund_rules.py    # 确定性退款资格规则（无 I/O、无副作用）
├── policies/
│   └── refund_policy.md   # 演示售后政策 v1.0
├── tests/
│   ├── test_orders.py             # 原有订单 API 测试
│   ├── test_database_migration.py # 旧库升级/幂等性/兼容性测试
│   ├── test_refund_rules.py       # 规则单元测试
│   └── test_refund_api.py         # 资格查询 API 测试
├── data/
│   └── flowpilot.db       # 本地 SQLite（不提交到 Git）
├── .gitignore
└── README.md
```

## 环境要求

- Windows 11 + PowerShell（当前开发环境）
- Python 3.12（实测 3.12.10）
- FastAPI 0.165.0
- pytest 9.2.0
- httpx 0.28.1（FastAPI `TestClient` 依赖）
- SQLite 3.49.1（Python 标准库自带）

无需额外数据库服务，也无需新增第三方业务依赖。

## 安装

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pytest httpx
```

如果 PowerShell 阻止激活脚本，可只对当前窗口放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 初始化数据库

```powershell
.\.venv\Scripts\python.exe -m backend.database
```

该命令会：

1. 创建 `data/` 目录和 `orders` 表（如果不存在）；
2. 如果旧库缺少 `delivered_at` 列，执行一次 `ALTER TABLE ... ADD COLUMN`；
3. 插入演示订单 `A1001`（已存在则跳过，不覆盖任何数据）。

演示订单：

| 字段 | 值 |
| --- | --- |
| order_id | A1001 |
| customer | Alice |
| product | Keyboard |
| amount_cents | 19900 |
| status | delivered |
| delivered_at | `NULL` |

`delivered_at` 故意留空：缺少交付日期时，规则会返回 `needs_review`。
如需演示“30 天内”的场景，可手动写入日期（参数化 SQL，仅改这条演示数据）：

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c = sqlite3.connect('data/flowpilot.db'); c.execute('UPDATE orders SET delivered_at = ? WHERE order_id = ?', ('2026-11-01', 'A1001')); c.commit(); c.close()"
```

## 启动 API

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload
```

- 服务地址：<http://127.0.0.1:8000>
- 交互文档：<http://127.0.0.1:8000/docs>

> 应用启动时会自动调用 `init_db()`，所以全新安装和旧数据库都能直接启动。

## API

### GET /orders/{order_id}

返回订单原始字段；订单不存在时返回 `404 {"detail": "Order not found"}`。

```powershell
Invoke-RestMethod http://127.0.0.1:8000/orders/A1001
```

响应示例（`delivered_at` 可能为 `null`）：

```json
{
  "order_id": "A1001",
  "customer": "Alice",
  "product": "Keyboard",
  "amount_cents": 19900,
  "status": "delivered",
  "delivered_at": null
}
```

### GET /orders/{order_id}/refund-eligibility

只读的退款资格筛查接口。它不会修改订单、不会创建工单、不会执行退款。

- 订单不存在：`404 {"detail": "Order not found"}`
- 订单存在：返回 `eligible`、`ineligible` 或 `needs_review`

```powershell
Invoke-RestMethod http://127.0.0.1:8000/orders/A1001/refund-eligibility
```

缺少交付日期时（演示订单的默认状态）：

```json
{
  "order_id": "A1001",
  "status": "needs_review",
  "reason": "Order has no delivery date; the policy requires human review instead of an automatic rejection.",
  "policy_version": "1.0",
  "policy_reference": "policies/refund_policy.md#refund-eligibility-rules",
  "evaluated_on": "2026-11-25",
  "days_since_delivery": null
}
```

30 天内（示例：交付日 2026-11-01，评估日 2026-11-25，第 24 天）：

```json
{
  "order_id": "A1001",
  "status": "eligible",
  "reason": "Order was delivered on 2026-11-01 (24 days ago, day 24); within the 30-day refund window; the deadline is 2026-12-01. Eligible to enter human approval, not approved.",
  "policy_version": "1.0",
  "policy_reference": "policies/refund_policy.md#refund-eligibility-rules",
  "evaluated_on": "2026-11-25",
  "days_since_delivery": 24
}
```

超过 30 天（示例：交付日 2026-10-20，评估日 2026-11-25，第 36 天）：

```json
{
  "order_id": "A1001",
  "status": "ineligible",
  "reason": "Order was delivered on 2026-10-20 (36 days ago, day 36); the 30-day refund window ended on 2026-11-19 (day 30 was the last eligible day).",
  "policy_version": "1.0",
  "policy_reference": "policies/refund_policy.md#refund-eligibility-rules",
  "evaluated_on": "2026-11-25",
  "days_since_delivery": 36
}
```

## 退款资格规则摘要

完整条款见 [`policies/refund_policy.md`](policies/refund_policy.md)。核心约定：

| 项目 | 约定 |
| --- | --- |
| 时间粒度 | 日期（不存时分秒） |
| 时区 | UTC |
| 交付当天 | 第 0 天 |
| 窗口 | `0 <= 天数 <= 30` |
| 第 30 天 | ✅ 仍符合时间要求 |
| 第 31 天 | ❌ 不符合时间要求 |
| 缺失/空白/格式错误/未来日期 | `needs_review` |
| 非 `delivered` 状态 | `needs_review` |
| 订单不存在 | 规则层 `needs_review`；HTTP 层 404 |

三种结果：

| 结果 | 含义 |
| --- | --- |
| `eligible` | 符合演示政策，可以进入人工审批；**不是**已批准退款 |
| `ineligible` | 数据完整有效，且可以确定不符合政策（已交付且第 31 天及以后） |
| `needs_review` | 信息缺失、无效、异常，或状态不适合自动判断；必须人工审核 |

**信息不足永远不会被自动判定为 `ineligible`。**

规则函数 `evaluate_refund_eligibility(order, as_of=...)` 接收订单字典和可注入的
评估日期，不访问数据库、不产生资金副作用；`get_refund_eligibility()` 只负责
从 SQLite 读取一条订单，再把数据交给纯函数。

## 数据库迁移

### 问题

Milestone 1 的数据库已经有 `orders` 表，且**没有** `delivered_at` 列。
只修改 `CREATE TABLE IF NOT EXISTS` 不会给已存在的表加字段——表已存在时该语句
直接跳过。因此必须显式迁移。

### 方案

`backend/database.py` 在 `init_db()` 中执行：

1. `CREATE TABLE IF NOT EXISTS orders (...)`：全新安装时直接建出带
   `delivered_at TEXT` 的表；
2. `PRAGMA table_info(orders)`：读取真实列名；
3. 如果缺少 `delivered_at`，执行 `ALTER TABLE orders ADD COLUMN delivered_at TEXT`；
4. 如果列已存在，什么都不做；
5. 并发启动时，另一个进程可能已经加列，捕获 `duplicate column name` 并视为成功。

### 为什么安全

- 只做 **ADD COLUMN**，不 DROP、不重建表、不复制表；
- 新列可空，旧行默认 `NULL`，不需要也不应该编造交付日期；
- 迁移可重复执行，重复运行不会改变数据；
- 旧订单字段和 `GET /orders/{order_id}` 的返回结构保持兼容，只是多了一个
  `delivered_at` 字段；
- 测试用真实的 5 列旧表结构建库，验证升级后原有行逐字段不变。

> 建议在升级重要数据库前先备份：
> `Copy-Item data\flowpilot.db data\flowpilot.db.bak`。
> 本项目只支持这种增量迁移；将来如果需要删列、改类型或重建表，应引入正式的
> schema version 表与迁移框架，而不是继续堆 `ALTER TABLE`。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

实测结果：**53 passed**（1 条第三方弃用警告，见下）。

覆盖范围：

- 原有订单查询 API（存在 / 不存在）；
- 第 0、1、14、29、30 天为 `eligible`；
- 第 30 天边界文案与第 31 天 `ineligible`；
- 缺失、空白、格式错误、不可能日期、未来日期；
- 非 `delivered` 状态；
- 订单不存在；
- 旧 5 列数据库升级后数据不丢失、字段值不变；
- `init_db()` 重复运行不破坏数据；
- `seed_order()` 不覆盖已有订单；
- 旧库升级后订单 API 与资格 API 均可用；
- 资格接口只读、重复调用结果一致；
- `eligible` / `ineligible` / `needs_review` 三种 HTTP 响应。

测试全部通过 `tmp_path` + `monkeypatch` 改写 `database.DB_PATH` 使用临时数据库，
不会读写 `data/flowpilot.db`。

已知警告：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated;
install `httpx2` instead.
```

这是 FastAPI/Starlette 测试客户端的上游弃用提示，不影响当前测试结果。后续升级
FastAPI/Starlette 时再处理，不在本次任务中引入新依赖。

## 明确未实现

以下能力属于后续里程碑，当前代码**没有**实现：

- LLM 推理与工具调用；
- RAG / 售后政策向量检索；
- 人工审批界面与审批状态机；
- 售后工单创建；
- 操作审计日志；
- 真实退款、支付网关或任何资金操作；
- React 前端；
- 登录、鉴权、多租户与权限控制；
- 生产级数据库（当前为单文件 SQLite）。

## 安全与限制

- 资格判断是**只读**的，不写订单、不写工单、不调用支付接口。
- AI 不能绕过人工审批；`eligible` 只是“可提交审批”。
- 演示政策不是真实企业条款或法律建议。
- `delivered_at` 以 TEXT 存储，数据库层没有日期 CHECK 约束；格式与合法性由
  `backend/refund_rules.py` 校验，异常一律进入 `needs_review`。
- 时区固定为 UTC；如未来改为业务时区，必须发布新政策版本并同步修改代码与测试。
- 未做并发压力测试；`busy_timeout` 只是减轻 SQLite 写锁冲突，不等同于生产级
  并发方案。

## 版本记录

| 版本 | 内容 |
| --- | --- |
| Milestone 1 | FastAPI + SQLite + 订单查询 API + 基础测试 |
| Milestone 2 | 售后政策 v1.0 + `delivered_at` 增量迁移 + 退款资格规则 + 只读资格 API + 测试与文档 |
