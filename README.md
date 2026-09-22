# 客服 Copilot 工作台

> **可交互 Demo**：https://copilot-workspace-xi.vercel.app
> **完整源码（GitHub）**：https://github.com/kkkkkkatherine01/Copilot-Workspace

电商平台客服辅助系统：客服与用户对话时，系统从 FAQ 知识库中检索相关内容，调用 Claude 生成回复建议；
客服可以采纳、编辑后发送、或忽略这条建议，处理结果记录到反馈日志，形成"生成 → 人工确认 → 留痕"的闭环。

核心设计原则：**LLM 只负责生成建议，不直接执行任何影响用户的动作**。采纳/编辑/发送必须经客服确认才生效，
每一次人工决策都会被记录，不存在"LLM 自动回复用户"的路径。

## 目录

- [系统架构](#系统架构)
- [技术选型理由](#技术选型理由)
- [项目结构](#项目结构)
- [FAQ 数据说明](#faq-数据说明)
- [启动方式](#启动方式)
- [知识溯源与FAQ匹配度](#知识溯源与faq匹配度)
- [检索准确率报告](#检索准确率报告eval-py)
- [已知限制](#已知限制)
- [部署](#部署)

## 系统架构

```
用户消息（前端输入框，或从测试场景加载）
   │  POST /api/suggest { conversation_id, user_message, history }
   ▼
若消息看起来依赖上下文（短句/含"这""那"等指代词，且有历史）：
   先用 generation.rewrite_query_with_history() 把它改写成独立完整的问题（仅用于检索，
   不影响后面生成阶段看到的原始用户消息）
   ▼
检索模块 retrieval.py
   将（改写后或原始的）消息编码为向量（本地模型 shibing624/text2vec-base-chinese），
   与 30 条 FAQ 的预计算向量做 cosine similarity，取 top-3
   ▼
生成模块 generation.py
   把「用户消息 + 历史对话（如有）+ top-3 FAQ」组装进 prompt，调用 Claude Haiku
   - 只能基于检索到的 FAQ 内容作答，不能编造
   - 必须标注引用的 FAQ id（用于前端知识溯源展示）
   - FAQ匹配度（检索相似度）低于阈值(0.5)时不调用 LLM，直接返回固定的"建议人工核实"文案
   ▼
后端 main.py 返回 { suggestion, retrieved_faqs, referenced_faq_ids, confidence, low_confidence }
   ▼
前端展示：左侧对话流 + 右侧建议面板（可编辑文本框 / 知识溯源卡片 / FAQ匹配度标签 / 三个操作按钮）
   ▼
客服点击 采纳 / 编辑后发送 / 忽略
   │  POST /api/feedback
   ▼
写入 SQLite feedback_log（记录 action、最终发送内容、检索到的FAQ、匹配度分数等）
```

## 技术选型理由

| 选型 | 原因 |
|---|---|
| **FastAPI + React 前后端分离** | 原始 Spec 最初定的是 Streamlit，后确认题目要求"含前后端"，改为真正的前后端分离架构：FastAPI 提供纯业务逻辑的 REST API，React 负责交互界面，职责边界更清楚 |
| **embedding 用 `shibing624/text2vec-base-chinese`** | FAQ 和用户消息都是中文，sentence-transformers 官方的 `all-MiniLM-L6-v2` 主要面向英文语料，对中文语义的区分度差；换成中文专门优化的模型后 `eval.py` 的检索命中率有实质提升 |
| **检索用 numpy 暴力计算 cosine similarity，不引入向量数据库** | FAQ 只有 30 条，暴力计算对这个数据量级没有性能问题，引入 FAISS 等向量库是不必要的复杂度 |
| **生成用 Claude Haiku** | Haiku 延迟低、成本低，适合这种"检索约束下的短回复生成"场景 |
| **反馈日志用 SQLite，对话历史不落库** | 反馈日志（`feedback_log`）需要持久化留痕，用 SQLite 足够；对话历史目前只在前端 state 里维护，属于 demo 场景下的合理取舍——刷新页面清空是可接受的，避免为了持久化对话记录再引入一张表和相应的读写逻辑 |
| **后端部署 Railway（不用 Render）** | Render 免费层是 ephemeral filesystem，服务休眠/重启会清空 SQLite 文件，直接导致反馈日志在评审时被清空；Railway 免费 Trial（1GB RAM、无自动休眠）没有这个问题，见[已知限制](#已知限制) |

## 项目结构

```
backend/
  data/
    faq.json                 # 30条FAQ知识库
    test_conversations.json  # 5条测试对话，用于demo演示和eval.py验证
  retrieval.py                # 向量检索：FaqIndex 类，embedding编码 + cosine相似度 + top-k
  generation.py                # 生成：prompt组装（V1/V2两版）、调用Claude API、引用解析
  db.py                         # SQLite反馈日志读写
  models.py                     # FastAPI请求/响应的Pydantic模型
  main.py                       # FastAPI应用、路由、CORS
  eval.py                       # 用test_conversations.json验证检索准确率
  tests/                         # pytest单元测试（引用解析、低置信度短路、编码策略、匹配度对齐）
  requirements.txt
  requirements-dev.txt           # 额外含pytest，仅本地/CI测试用
frontend/
  src/
    App.jsx                     # 主布局与状态管理
    components/
      ConversationPanel.jsx     # 左侧：对话流 + 输入框 + 加载测试场景
      SuggestionPanel.jsx       # 右侧：建议文本框 + 知识溯源 + FAQ匹配度 + 操作按钮
    api.js                       # 封装对后端API的调用
PROMPT_ITERATION.md              # Prompt V1/V2 对比记录
BAD_CASE_ANALYSIS.md             # 2个真实bad case分析
DEMO_LINK.txt                     # Demo/源码链接，供压缩包提交时在根目录直接看到
```

## FAQ 数据说明

题目原文里 FAQ 知识库写的是"共 20 条"，但题目只给出了 5 条作为示例，完整的 20 条
内容并未随题目提供。本项目实际使用的 `faq.json` 共 30 条，覆盖题目给出的 5 个分类（退换货、
物流配送、优惠促销、账户安全、支付问题），并新增了发票问题、会员权益 2 个分类，是在题目基础
上自行扩充的，不是题目原始数据。

## 启动方式

### 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows；Mac/Linux 用 source venv/bin/activate

# 先单独装CPU版torch，避免默认拉取体积过大的GPU版
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

cp .env.example .env           # 然后把 ANTHROPIC_API_KEY 填进 .env
uvicorn main:app --reload --port 8000
```

首次启动会从 HuggingFace 下载 embedding 模型权重（约几百MB），需要能访问 huggingface.co。

### 前端

```bash
cd frontend
npm install
cp .env.example .env.local     # 默认 VITE_API_BASE_URL=http://localhost:8000 即可本地联调
npm run dev
```

打开 `http://localhost:5173`，后端需要保持在 8000 端口运行。

### 验证检索准确率

```bash
cd backend
python eval.py
```

### 运行单元测试

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

测的是 `generation.py` 的引用解析、低置信度短路逻辑、`retrieval.py` 的编码策略，以及
`main.py` 的匹配度展示对齐逻辑，都是纯逻辑测试，用 mock 替换了 Anthropic 客户端，不产生
真实API调用。检索的端到端准确率由 `eval.py` 覆盖。

## 知识溯源与FAQ匹配度

- **知识溯源**：`/api/suggest` 返回 `retrieved_faqs`（检索到的 top-3 FAQ 原文）和 `referenced_faq_ids`
  （生成阶段实际引用了哪几条，从 Claude 输出末尾的 `[参考: faq_001, ...]` 标记解析得到），前端在FAQ卡片上
  标出"已引用"，方便客服核对建议依据。

- **FAQ匹配度**（对应原文的加分项"置信度展示"）：数值对应实际被 Claude 引用的那条 FAQ 的
  cosine similarity 分数（如果引用了多条，取最高分；没有任何FAQ被引用时，比如置信度过低未调用LLM，
  退回显示检索最高分），前端映射成高(≥70%)/中(≥50%)/低(<50%) 三档，低于 0.5 时后端直接不调用 LLM，
  返回固定的"建议人工核实"文案。这是检索相似度，不是校准过的正确率概率，命名上用"匹配度"而不是
  "置信度"以避免混淆。

## 检索准确率报告（eval.py）

分别报告 Top-1 准确率和 Top-3 召回率：

```
conv_001   [easy  ] expected=faq_001  top1=faq_001  score=0.581  top1=HIT   top3=HIT
conv_002   [easy  ] expected=faq_002  top1=faq_002  score=0.649  top1=HIT   top3=HIT
conv_003   [medium] expected=faq_003  top1=faq_013  score=0.599  top1=MISS  top3=HIT
conv_004   [medium] expected=faq_004  top1=faq_004  score=0.788  top1=HIT   top3=HIT
conv_005   [hard  ] expected=faq_005  top1=faq_005  score=0.637  top1=HIT   top3=HIT

Top-1 Accuracy: 4/5 (80%)
Top-3 Recall:   5/5 (100%)
```

conv_003 的 Top-1 miss 属于三条语义高度相似的优惠券FAQ互相"抢答"，正确答案排第3（分数只差
0.01~0.05）；但它进了 Top-3，生成阶段实际最终回复引用的是正确的 faq_003。详细分析见
[BAD_CASE_ANALYSIS.md](BAD_CASE_ANALYSIS.md)。

## 已知限制

1. **检索本身不感知对话历史**：只有系统判断消息可能依赖上下文时才会先改写成独立问题再检索，
   改写效果依赖LLM输出，不保证每次都命中最优排序。详见 `BAD_CASE_ANALYSIS.md` Case 2。
2. **对话历史不持久化**：刷新页面会丢失（反馈日志本身是持久化的，不受影响）。
3. **检索准确率评测样本量小**：只有题目提供的 5 条测试对话，Top-1/Top-3 数字的统计意义有限。
4. **Railway 免费 Trial 有时间限制**：30天/$5额度用完后会降级，不是永久免费方案，仅覆盖"评审窗口内可访问"
   这个场景。

## 部署

- **可交互 Demo**：https://copilot-workspace-xi.vercel.app
- 后端：https://copilot-workspace-production.up.railway.app （Railway，Root Directory 设为 `backend`，
  挂载 Persistent Volume 到 `/data` 存放 SQLite 文件，`DB_PATH=/data/feedback.db`）
- 前端：Vercel，Root Directory 设为 `frontend`，环境变量 `VITE_API_BASE_URL` 指向上面的 Railway 地址
- 后端 CORS 白名单通过环境变量 `FRONTEND_ORIGIN` 加上了 Vercel 的域名
- **持久化已实测验证**：写入一条反馈记录后手动重启 Railway 服务，重启后数据仍在（用临时调试接口验证过，
  验证完已移除，不是正式对外的API）
