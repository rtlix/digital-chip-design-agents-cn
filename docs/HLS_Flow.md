# 高层综合（HLS）流程 — 完整架构设计
## Orchestrator + Stage Agents + Skills

> **目的**：AI 驱动的 HLS 流程，把 C/C++/SystemC 算法描述转换为 RTL，连接软件与硬件两端。覆盖算法分析、HLS directive 规划、RTL 质量检查和 co-simulation 验证。

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    HLS ORCHESTRATOR                          │
│  输入：C/C++ algorithm、performance/area target、TB           │
│  输出：与 golden C model 匹配的已验证 RTL                       │
└────────────────────────┬─────────────────────────────────────┘
                         │
     ┌───────────────────┼───────────────────────┐
     ▼                   ▼                       ▼
  Algorithm          HLS Synthesis          Co-simulation
  Analysis           Agent                  Agent
     │                   │                       │
  SKILL              SKILL                   SKILL
```

---

## 2. 共享状态对象

```json
{
  "run_id": "hls_001",
  "design_name": "fft_block",
  "inputs": {
    "source_files":    ["fft.cpp", "fft.h"],
    "testbench":       "fft_tb.cpp",
    "golden_output":   "golden.dat",
    "target_freq":     "500MHz",
    "target_latency":  "256 cycles",
    "target_area":     "50K gates",
    "interface":       "AXI4-Stream",
    "tool":            "Vitis_HLS | Catapult | Stratus"
  },
  "stages": {
    "algorithm_analysis":  { "status": "pending", "output": {} },
    "directive_planning":  { "status": "pending", "output": {} },
    "hls_synthesis":       { "status": "pending", "output": {} },
    "rtl_qc":              { "status": "pending", "output": {} },
    "cosimulation":        { "status": "pending", "output": {} },
    "hls_signoff":         { "status": "pending", "output": {} }
  },
  "hls_report": {
    "latency_cycles": null,
    "ii":             null,
    "area_lut":       null,
    "area_ff":        null,
    "area_dsp":       null
  },
  "cosim_match": null,
  "flow_status": "not_started"
}
```

---

## 3. Stage Sequence（阶段顺序）

```
[Algorithm Analysis] ──► [Directive Planning] ──► [HLS Synthesis]
                                 ▲                       │ targets not met
                                 └───────────────────────┘
                                                         │ targets met
                              ▼
                        [RTL QC] ──► [Co-simulation]
                                           │ mismatch with golden
                                           └──► Algorithm Analysis
                                           │ match
                                      [HLS Sign-off]
```

### Loop-Back Rules

| 失败 | 回退到 | 最大次数 |
|---|---|---:|
| Latency > target | Directive Planning | 4 |
| Area > target | Directive Planning | 3 |
| 需要 pipeline 时 II >1 | Directive Planning | 3 |
| Co-sim output mismatch | Algorithm Analysis | 2 |
| RTL QC 推断 latch | Directive Planning | 2 |

---

## 4. Skill 文件说明

### 4.1 `sv-hls-algorithm/SKILL.md`

```markdown
# Skill: HLS — Algorithm Analysis

## Purpose
在综合前分析 C/C++ source，找出 HLS-friendly 与 HLS-hostile pattern。

## HLS-Friendly Patterns
- Fixed-size array，避免 dynamic allocation
- 规则 loop bound
- Integer arithmetic
- 可 pipeline 的 loop
- Power-of-2 array size，有利于 memory banking

## HLS-Hostile Patterns
1. malloc/new → static array
2. Recursive function → iterative
3. Pointer aliasing → restrict 或重构
4. printf/file I/O → 删除或 #ifdef guard
5. Function pointer → switch/case
6. Data-dependent loop bound → max bound + early exit
7. Floating point → 评估 fixed-point（ap_fixed<>）

## Performance Analysis
1. 找 critical loop
2. Minimum latency = trip count × body latency
3. 找 loop-carried dependency，决定 II 下限
4. 区分 sequential/burstable 与 random memory access

## QoR Metrics
- HLS-hostile pattern 全处理
- Critical loop 完成 dependency analysis
- Memory access pattern 已记录

## Output Required
- Algorithm analysis report
- Fixed-point type 建议
- Critical loop dependency graph
```

---

### 4.2 `sv-hls-directives/SKILL.md`

```markdown
# Skill: HLS — Directive Planning

## Purpose
选择 HLS pragma/directive，满足 latency、throughput（II）和 area target。

## Core Directives

### Throughput / Pipelining
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

### Memory / Interfaces
```cpp
#pragma HLS ARRAY_PARTITION variable=buf cyclic factor=4
#pragma HLS ARRAY_RESHAPE variable=buf cyclic factor=4
#pragma HLS INTERFACE mode=axis port=data
#pragma HLS INTERFACE mode=m_axi port=mem
```

### Resource Binding
```cpp
#pragma HLS BIND_OP variable=result op=mul impl=fabric
#pragma HLS BIND_OP variable=result op=mul impl=dsp
#pragma HLS ALLOCATION operation=mul limit=4
```

## Directive Strategy by Target
| Target | 主要 Directive |
|---|---|
| Low latency | UNROLL、PIPELINE II=1 |
| High throughput | PIPELINE + DATAFLOW + ARRAY_PARTITION |
| Low area | ALLOCATION limit、resource sharing、no unroll |
| Balanced | Inner-loop PIPELINE II=1 + ARRAY_PARTITION |

## QoR Metrics
- Achieved II ≤ target II
- Latency ≤ target cycles
- Area 在 budget 内
- Directive 不产生 synthesis error

## Output Required
- Annotated source
- Directive justification table
- HLS report 预期 QoR
```

---

### 4.3 `sv-hls-cosim/SKILL.md`

```markdown
# Skill: HLS — Co-simulation and Verification

## Purpose
验证生成的 RTL 与原始 C/C++ golden model 功能等价。

## Co-simulation Flow
1. HLS tool 生成 SystemC/Verilog simulation wrapper
2. C testbench 通过 wrapper 驱动 RTL
3. 自动比较 RTL output 与 C golden
4. 可输出 waveform 调试

## Verification Requirements
1. Testbench 覆盖全部 code path
2. Corner：max、zero、overflow
3. Back-to-back transaction
4. 实测 RTL latency vs HLS report
5. 实测 II vs HLS report

## Common Co-sim Failures
- AXI handshake mismatch → 修 interface directive
- Fixed-point overflow → 增加 bit width
- C/RTL initialization 不一致 → 对齐 reset
- Loop exit mismatch → 检查 data-dependent bound

## QoR Metrics
- Co-sim 与 golden 100% match
- Latency 与 HLS report 差异 ≤5%
- II 完全匹配
- 无 simulation error / X propagation

## Output Required
- Co-sim pass/fail report
- Latency/II measurement
- Failure waveform
```

---

## 5. Orchestrator System Prompt

```
You are the HLS Orchestrator.

You guide the conversion of C/C++ algorithms to verified RTL through
analysis, directive optimization, and co-simulation validation.

STAGE SEQUENCE:
  algorithm_analysis → directive_planning → hls_synthesis →
  rtl_qc → cosimulation → hls_signoff

LOOP-BACK RULES:
  - hls_synthesis: latency > target        → directive_planning (max 4x)
  - hls_synthesis: area > target           → directive_planning (max 3x)
  - hls_synthesis: II > target             → directive_planning (max 3x)
  - cosimulation: mismatch                 → algorithm_analysis (max 2x)
  - rtl_qc: latch inferred                 → directive_planning (max 2x)

Track hls_report metrics in state_object.hls_report.
Output: Co-simulation verified RTL + interface documentation for RTL flow.
```

> 固定 stage 名、枚举和机器接口保留英文。
