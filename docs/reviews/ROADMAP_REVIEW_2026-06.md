# Roadmap 与进展评审 — 2026 年 6 月

这是对 `FUTURE_WORK.md` 路线图（14 项；9 项已交付、5 项开放）
以及仓库当前状态的一次多视角评审。评审由三个相互独立的角色完成：

- **Implementation Auditor**：标记为 “shipped” 的内容是否真的有代码/产物支撑？
- **QA & CI Reviewer**：当前进展是否有足够回归保护？
- **Product & Roadmap Strategist**：路线图本身的管理方式是否健康？

**评审仓库状态：** commit `f6ba8dc`（PR #61 merge），package version 1.3.0，
design_state `format_version` 1.5。

---

## TL;DR

这份路线图整体上非常诚实，而且执行质量高：所有标为 shipped 的项目都能在仓库中找到真实产物，
前置依赖也基本按正确顺序交付，format_version 从 1.1 → 1.5 的演进在 schema、CHANGELOG、
fixture 和全部 15 个 Orchestrator 中保持一致。

三个评审视角独立得出的共同薄弱点是：

**验证停留在“结构正确”，系统尚未真正通过实际使用证明。**

当前 CI 主要检查 schema/文件结构，不检查 prompt 内容质量或运行行为；
安装路径几乎未测试；experience record 仍为空，因此 Memory subsystem 虽然实现完整，
却没有真正用真实数据跑过。

因此下一阶段价值最高的工作，不是继续加功能，而是**实际运行并验证现有系统**。

---

## 视角 1 — Implementation Audit：标记为 shipped 的内容真实吗？

**结论：VERIFIED，仅发现一处文档数量不一致。**

| Item | Claim | 状态 | Evidence |
|---|---|---|---|
| 1 | Memory-keeper Skill | ✅ Verified | `plugins/infrastructure/skills/memory-keeper/SKILL.md` + `distill.py` |
| 3 | QoR trending | ✅ Verified | `tools/qor_trends.py` |
| 4 | Infrastructure Memory | ✅ Verified | `memory/infrastructure/`、opt-in 环境键控行为、`VALID_DOMAINS` |
| 5 | Central design state | ⚠️ Verified，有文档差异 | 全 15 个 Orchestrator 读写 `design_state.json`；但 FUTURE_WORK 当时写成 “14 orchestrators” |
| 6 | Continuous verification loop | ✅ Verified | `plugins/meta/agents/pipeline-orchestrator.md` + fix_request schema |
| 7 | Agent contract standardization | ✅ Verified | 全部 Orchestrator 有 confidence/failure_class/suggested_next_step |
| 8 | Constraint awareness | ✅ Verified | 11 个 Skill 使用 `design_state.constraints.<key>` |
| 10 | Structured failure handling | ✅ Verified | 全部 Orchestrator 使用 retry_strategy 映射 |
| 11 | Checkpoints + observability | ✅ Verified | checkpoints / approved_checkpoints / pending_approval |
| 14 | `route_to` reserved | ✅ 与说明一致 | Schema 中存在，但 dispatch logic 还未消费 |

**小问题：**
`constraint_ref` 在 `memory/README.md` 和 Orchestrator 文档里有说明，
但没有正式加入 schema 的 `historyEntry` 定义，只是因为
`additionalProperties:true` 才能合法通过。

**做得好的地方：**
仓库没有明显过度宣传。
每个 ✓ 项都能映射到真实 artifact，
而且 format_version 演进链条清晰：

- 1.1：fix_requests
- 1.2：output contract
- 1.3：checkpoint
- 1.4：constraints
- 1.5：retry_strategy

---

## 视角 2 — QA & CI：这些进展是否有足够回归保护？

### 做得好的地方

- **Manifest/path validation**：
  `validate.yml` 会检查 plugin.json 结构、path traversal、文件存在、marketplace cross-reference 和数量一致性。
- **Schema validation 有正反 fixture**：
  `plugins/meta/skills/pipeline-orchestration/examples/` 下 fixture 自动加入 CI。
- **结构化检查**：
  检查全部 Skill 和 Orchestrator 所需 frontmatter/section。
- **23 个 pytest case**：
  覆盖 `distill.py` 和 `qor_trends.py` 的 malformed JSONL、regression detection、
  threshold、CLI exit code 等。
- **CI dependency 固定版本**：
  jsonschema 4.23.0、pytest、Python 3.11。

### 缺口（按风险排序）

1. **CRITICAL — Skill 内容本身没有验证。**  
   CI 只检查 `## Domain Rules`、`## QoR Metrics` 等 section 是否存在，
   不检查里面是不是空、规则是否可执行、metric 有没有单位。
   而本产品的核心就是这些 Markdown prompt。
   因此 prompt 内容退化目前完全可能在绿 CI 下发布。

2. **CRITICAL — 安装路径没有测试。**  
   `install.sh`、`install.ps1`、`bin/install.mjs`、`bin/detect.mjs`
   有 500+ 行逻辑，但几乎没有跨平台 CI 验证。
   这是每个用户第一步就会碰到的代码。

3. **HIGH — 缺少跨文档/reference validation。**  
   仓库有大量 Markdown，没有自动检查内部链接、路径、anchor、数量描述是否漂移。
   FUTURE_WORK 的 “14 orchestrators” 数量错误正是这类问题。

4. **MEDIUM-HIGH — 缺少 lint/type check。**  
   Python 没有 ruff/mypy/pylint，`bin/*.mjs` 也没有 eslint/prettier。

5. **MEDIUM — Schema regression coverage 偏薄。**  
   只有一个主要 negative fixture，
   缺少 1.1–1.4 backward-compat fixture；
   也缺 write→distill→trend 的 end-to-end Memory cycle test。

**总结：**
当前 CI 对“数据格式”保护较强，
对真正产品表面——prompt 内容与安装体验——保护较弱。

---

## 视角 3 — Product & Roadmap Strategy：流程是否健康？

### 做得好的地方

- **前置依赖图明确而且真的被遵守。**
  Item 5（design_state）先落地，之后才是 6 → 7 → 8/10/11。
- **状态管理清楚。**
  已完成项目说明 artifact 在哪里，
  item 14 也诚实注明 “schema reserved” 而不是假装已经被 dispatch logic 使用。
- **CHANGELOG 是真正的进度账本。**
  与 format_version 演进有对应关系。

### 缺口（按优先级）

1. **P0 — 没有 issue-tracker 关联。**  
   FUTURE_WORK 写着要作为 follow-up issue 跟踪，但当时没有真正建立 issue。
   Open item 2、9、12–14 都只是 prose，
   缺少状态、用户反馈和 velocity 可见性。

2. **P0 — experience record 为 0。**  
   `memory/` 下只有 seeded `knowledge.md`，
   没有真实 `experiences.jsonl`。
   因此两级 Memory、memory-keeper、qor_trends
   都“代码完成但实践未验证”。

3. **P1 — Item 9 实际处于 partial。**  
   `architecture.candidates[]` 已进 schema/fixture，
   但 Agent 不会真正填充；
   `refinement_needed` re-entry 和 memory field 也未实现。
   更准确状态应是：
   “schema ready，agent behavior pending”。

4. **P1 — 缺少 worked end-to-end example。**  
   文档很全，但没有一套 known-good reference run，
   比如 sky130 小 counter/multiplier 从 spec 一路跑到每阶段的 `design_state.json`。

5. **P1 — 没有 Agent 输出质量 benchmark，也没有真正 EDA integration regression。**  
   当前只验证 schema-valid，
   不能证明生成 RTL 真能综合、timing 能 closure、release 间质量不退化。
   这是路线图中最大的战略空白之一。

6. **P2 — 其他流程债务。**
   - item 14 没明确标注 blocked by 12/13
   - IDE target 缺 drift protection
   - 缺 format_version migration guide
   - 缺 EDA licensing/cost matrix
   - plugin 数量继续增长后 Marketplace discoverability 会变差

---

## 跨视角综合结论

**共同优点：执行纪律强。**

已标记 shipped 的内容确实存在，
依赖顺序基本正确，
schema/data contract 有真实 CI 保护。

**共同缺点：验证停留在结构层，系统还没有充分用真实工程证明。**

三个视角分别指出：

- Auditor：文档漂移依赖人工纪律，而不是 CI
- QA：prompt 内容和 install behavior 缺自动保护
- Strategy：Memory subsystem 尚未由真实 run 产生的数据验证

换句话说：

**架构已经领先于证据。**

因此建议在继续增加更多 domain/Agent 前，
优先做真实 end-to-end 使用、installer smoke test、prompt-content validation、
Memory 数据闭环和开源 EDA regression。

---

## 优先级建议

| Priority | Action | Roadmap 关联 |
|---|---|---|
| P0 | 为 open item 2、9、12、13、14 建 GitHub issue，并加 `roadmap` label | 落实 FUTURE_WORK 自己的流程要求 |
| P0 | 为 synthesis/PD/verification 准备每 domain 5–10 条 realistic experience，CI 中跑 memory-keeper + qor_trends | 真正验证 item 1/3，并启动 item 2 数据积累 |
| P1 | 把 item 9 改成 “in progress — schema ready, agent implementation pending” | 提高路线图准确性 |
| P1 | 新增 `docs/TUTORIAL.md`，给出每 stage 的 expected `design_state.json` | Onboarding + install validation |
| P1 | 在 CI 中 smoke-test installer，至少 Linux/macOS，覆盖 `npx` 和 `install.sh` | 关闭最大未测表面 |
| P1 | 增加 Skill 内容校验：非空 section、numbered rule、带单位 metric | 保护核心产品 |
| P2 | 增加 docs link/reference checker、ruff+mypy、MJS linter | 捕获数量/引用漂移 |
| P2 | 标记 item 14 blocked by 12/13；增加 EDA licensing/cost matrix；记录 format_version migration | 管理预期 |
| P3 | Nightly 跑 Yosys/OpenROAD + sky130，记录 WNS/area/coverage baseline | 长期质量 benchmark |
