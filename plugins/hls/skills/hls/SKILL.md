---
name: hls
description: >
  高层综合（HLS）——C/C++ 算法分析、HLS directive 优化、综合执行和协同仿真验证。
  适用于把 C/C++ 转成可综合 RTL、利用 pragma 优化 latency/throughput/area，
  或验证生成 RTL 与 golden C model 一致。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: High-Level Synthesis (HLS)（高层综合）

## Invocation
- **用户直接调用**并提出 HLS 任务时：立即启动 `digital-chip-design-agents:hls-orchestrator`，
  传入完整请求和上下文，不直接执行 stage。
- **由 hls-orchestrator 中途调用**时：不要再次启动 Agent；本文件作为只读规则库返回 stage rule、
  sign-off criteria 或 loop-back guidance。

## Pre-run Context
任何 stage 前，如存在则读取：
1. `memory/hls/knowledge.md`
2. `memory/hls/run_state.md`
并利用其中历史 failure pattern、tool flag 和当前 run state。

## Purpose
将 C/C++/SystemC 算法描述转换成可综合 RTL，覆盖 HLS 兼容性分析、pragma/directive
优化以及 co-simulation，保证 RTL 与 golden C model 一致。

---

## Supported EDA Tools
### Open-Source
- **Bambu HLS**（`bambu`）
- **LegUp HLS**
- **Calyx / Futil**
- **MLIR/CIRCT**（`circt-opt`）

### Proprietary
- **Xilinx Vitis HLS**（`vitis_hls`）
- **Cadence Stratus**（`stratus`）
- **Siemens Catapult**（`catapult`）

---

## Stage: algorithm_analysis

### HLS-Hostile Patterns
综合前必须处理：
1. Dynamic memory（malloc/new）→ 固定大小 static array
2. Recursive function → iterative + explicit stack
3. Pointer aliasing → `restrict` 或重构访问
4. System call（printf/file I/O）→ 用 `#ifndef __SYNTHESIS__` 包裹
5. Function pointer → switch/case dispatch
6. Data-dependent loop bound → 最大 bound + early-exit flag
7. Floating point → 评估 fixed-point，例如 Vitis 的 `ap_fixed<W,I>`

### Analysis Steps
1. 找到 innermost critical loop
2. 分析 loop-carried dependency，确定可达到的 II 下限
3. 将 memory access 分类为 sequential/burstable 或 random
4. 计算 theoretical minimum latency：trip_count × body_latency

### QoR Metrics to Evaluate
- HLS-hostile pattern 全部解决
- Critical loop 已建立 dependency graph
- 已计算 theoretical II lower bound

### Output Required
- Algorithm analysis report
- Fixed-point type 建议
- Critical loop dependency graph

---

## Stage: directive_planning

### Pipelining / Throughput
```cpp
#pragma HLS PIPELINE II=1
#pragma HLS DATAFLOW
#pragma HLS LOOP_FLATTEN
#pragma HLS LOOP_MERGE
```

### Latency / Unrolling
```cpp
#pragma HLS UNROLL factor=4
#pragma HLS UNROLL
```

### Memory / Interface
```cpp
#pragma HLS ARRAY_PARTITION variable=buf cyclic factor=4
#pragma HLS INTERFACE mode=axis port=data
#pragma HLS INTERFACE mode=m_axi port=mem
#pragma HLS INTERFACE mode=s_axilite port=ctrl
```

### Resource Binding
```cpp
#pragma HLS BIND_OP op=mul impl=dsp
#pragma HLS ALLOCATION operation=mul limit=4
```

### Strategy by Target
| Target | 主要 Directive |
|---|---|
| Low latency | UNROLL + PIPELINE II=1 |
| High throughput | PIPELINE + DATAFLOW + ARRAY_PARTITION |
| Low area | ALLOCATION limit + 不 UNROLL |
| Balanced | Inner-loop PIPELINE II=1 + ARRAY_PARTITION |

### QoR Metrics to Evaluate
- II ≤ `design_state.constraints.hls.target_ii`
- Latency ≤ `design_state.constraints.hls.target_latency_cycles`
- Area 在 budget 内
- 0 directive synthesis error

### Output Required
- 带 directive 和理由的 annotated source
- Directive justification table

---

## Stage: hls_synthesis

### Domain Rules
1. 在目标 clock period 下综合。
2. 检查 HLS report：latency、II、resource usage。
3. 与 target 比较，未达标则回到 directive planning。
4. 标记 unresolved dependency、failed II、inferred latch 等 warning。
5. 验证 interface protocol 与 system integration 要求一致。

### QoR Metrics to Evaluate
- II 满足 `constraints.hls.target_ii`
- Latency 满足 `constraints.hls.target_latency_cycles`
- Area 在 budget 内
- 无 latch inference warning

### Output Required
- HLS synthesis report
- Generated RTL
- Unresolved warning 与 justification

---

## Stage: rtl_qc

### Domain Rules
1. 对 HLS-generated RTL 运行与 rtl-design Skill 相同的 lint。
2. 确认无 latch。
3. Interface signal name 与 integration requirement 一致。
4. 所有 register reset 正确。

### QoR Metrics to Evaluate
- Lint error：0
- Inferred latch：0
- Interface port match：PASS

### Output Required
- HLS-generated RTL lint report

---

## Stage: cosimulation

### Domain Rules
1. C testbench 通过 HLS wrapper 驱动 RTL。
2. 自动将 RTL output 与 C golden model 比较。
3. 实测 latency/II，应与 HLS report 匹配。
4. 覆盖全部 code path 和 boundary condition。

### Common Failures
| Failure | Fix |
|---|---|
| Output mismatch | 检查 fixed-point overflow，增加 bit width |
| AXI handshake error | 修正 INTERFACE pragma |
| Latency 不一致 | 检查 loop bound 是否 static |
| X propagation | 初始化 C source 中所有 variable |

### QoR Metrics to Evaluate
- Co-sim output 与 C golden：100% match
- Latency 偏差 ≤ `constraints.hls.cosim_tolerance_pct`%，默认 5%
- II 与 HLS report 完全一致
- 无 simulation error / X propagation

### Output Required
- Co-simulation pass/fail report
- Latency/II measurement log

---

## Stage: hls_signoff

### Sign-off Checklist
- [ ] HLS-hostile pattern 全解决
- [ ] Achieved II ≤ target
- [ ] Latency ≤ target
- [ ] Area 在 budget 内
- [ ] RTL QC：lint clean、无 latch
- [ ] Co-sim：100% output match；latency 在 tolerance 内
- [ ] Interface port 符合 integration spec

### Output Required
- HLS RTL package（.v/.sv）
- Co-sim pass report
- HLS QoR report（latency、II、area）
- Interface documentation

---

## Constraint Validation
权威 schema 见 Meta Pipeline Skill。
进入 `algorithm_analysis` 时，`constraints.hls.target_ii` 与
`constraints.hls.target_latency_cycles` 至少一个必须非 null；两者同时存在时优先 target_ii。
Optional：`hls.cosim_tolerance_pct` 默认 5；`clock.clk_mhz` 如有则作为 synthesis target。

---

## Memory

### Write on stage completion
每 stage 完成后按 `run_id` upsert `memory/hls/experiences.jsonl`。
`run_id = hls_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用；
每条 JSON 必须包含匹配的顶层 `run_id`，最终 sign-off 前保持 `signoff_achieved:false`。

### Run state
工具执行前第一步写 `memory/hls/run_state.md`：
```markdown
run_id:      hls_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  <first stage name>
```
每 stage 后更新 `last_stage`。

### Optional: claude-mem index
如 `mcp__plugin_ecc_memory__add_observations` 可用，将 applied fix 写入
`chip-design-hls-fixes`；否则跳过，JSONL 为 canonical record。
