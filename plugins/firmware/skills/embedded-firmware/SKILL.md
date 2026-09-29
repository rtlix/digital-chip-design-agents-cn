---
name: embedded-firmware
description: >
  嵌入式固件与设备驱动——BSP 开发、UART/SPI/I2C/GPIO/DMA/Timer 等外设驱动、
  FreeRTOS/Zephyr 集成，以及系统验证。适用于芯片 bring-up firmware、HAL driver、
  RTOS 移植或在 FPGA/硅片目标上验证固件。
version: 1.0.0
author: chuanseng-ng
license: MIT
allowed-tools: Read, Write, Bash
---

# Skill: Embedded Firmware & Device Drivers（嵌入式固件与设备驱动）

## Invocation
当本 Skill 被加载且用户提出 firmware/BSP 任务时，**不要直接执行 stage**。
立即启动 `digital-chip-design-agents:firmware-orchestrator`，并传入完整请求与所有可用上下文。
Orchestrator 负责 stage sequence、loop-back 和 sign-off。

仅在 Orchestrator 中途读取本 Skill 获取阶段规则，或用户只问局部参考问题时，
才直接使用本文件中的 domain rule。

## Pre-run Context
执行或建议任何 stage 前，如存在则读取：
1. `memory/firmware/knowledge.md` —— 已知 failure pattern、有效 tool flag、PDK/tool quirks。
2. `memory/firmware/run_state.md` —— 当前 `run_id/design_name/tool/last_stage`，用于恢复中断流程。

## Purpose
指导 BSP 创建、外设驱动开发、RTOS 集成与系统级 firmware validation。
Firmware 是真实硅片最先运行的软件层，它的正确性是后续全部软件开发的基础。

---

## Supported EDA Tools

### Open-Source
- **GCC cross-compiler**（`arm-none-eabi-gcc`、`riscv64-unknown-elf-gcc`）—— bare-metal firmware 编译
- **OpenOCD**（`openocd`）—— 开源 on-chip debugger，支持 JTAG/SWD bring-up
- **GDB cross-debugger**（`arm-none-eabi-gdb`）—— 通过 OpenOCD 做源码级调试
- **QEMU**（`qemu-system-arm`、`qemu-system-riscv64`）—— 硬件可用前验证 firmware

### Proprietary
- **J-Link GDB Server**（`JLinkGDBServer`）—— SEGGER 高速 JTAG/SWD probe
- **Lauterbach TRACE32**（`t32marm`）—— bring-up 的硬件 trace/debug
- **Arm Development Studio**（`armds`）—— 集成 Arm compiler/debugger 的 IDE

---

## Stage: bsp_development

### Domain Rules
1. Startup code（`crt0.S` / `startup.c`）必须按顺序：
   - stack pointer 指向 linker script 的 `__stack_top`
   - 复制 `.data` LMA → VMA
   - 清零 `.bss`
   - 调用 `SystemInit()`
   - 跳转 `main()`
2. `SystemInit()` 顺序：power stable → PLL → clock mux → peripheral。
3. Interrupt controller：定义 vector table、IRQ enable/disable API、priority API。
4. `memory_map.h` 必须包含**全部** peripheral base address 与 register offset，禁止 magic number。
5. 所有硬件 register access 使用 `volatile` pointer。
6. 对硬件 register 的 atomic read-modify-write：关闭 IRQ 或使用 atomic op。
7. Hardware access sequence 周围使用 DMB/DSB 或等价 memory barrier。
8. BSP 必须与 RTOS 解耦，BSP layer 不调用 OS API。

### QoR Metrics to Evaluate
- Boot：芯片在预期时间到达 `main()`
- Clock：PLL 全部 lock，peripheral clock 正确
- Interrupt：vector table 有效，未处理 exception 会进入 default handler
- Memory：`.data` 正确初始化，`.bss` 清零，并通过 memory read 验证

### Common Issues & Fixes
| Issue | Fix |
|---|---|
| PLL 不 lock | 检查 reference clock source 与输入频率范围 |
| `main()` 前卡死 | 每个 init step 切换 debug LED 进行定位 |
| 启动时 stack overflow | 增大 linker script 中 `STACK_SIZE` |
| `.data` 未初始化 | 检查 crt0 LMA→VMA copy range 和 AT clause |

### Output Required
- `startup.S`、`system_init.c`
- 完整 `memory_map.h`
- Linker script
- BSP build system

---

## Stage: peripheral_drivers

### Driver Architecture（HAL pattern）
```c
status_t PERIPH_Init(PERIPH_Type *base, const periph_config_t *config);
status_t PERIPH_WriteBlocking(PERIPH_Type *base, const uint8_t *data, size_t len);
status_t PERIPH_TransferNonBlocking(PERIPH_Type *base, periph_handle_t *h, periph_xfer_t *x);
void     PERIPH_HandleIRQ(PERIPH_Type *base, periph_handle_t *handle);
```

### Domain Rules
1. 所有 register access 通过 `memory_map.h`，禁止 inline hex address。
2. 所有 polling loop 必须有 timeout counter，超时返回 error code。
3. 所有 operation function 返回 `status_t`，不要用 `void`。
4. 每个 driver 文档化 thread-safety；不安全时明确 mutex requirement。
5. 高 bandwidth peripheral 必须提供 DMA variant。
6. Low-power mode 提供 `suspend()/resume()` hook。
7. Async completion 使用 callback function pointer。

### Required Peripheral Coverage
| Peripheral | 关键测试 |
|---|---|
| UART | Baud rate、parity、TX/RX loopback、DMA |
| SPI | 4 种 mode、master/slave loopback、DMA |
| I2C | 7/10-bit address、repeated start、DMA |
| GPIO | Input/output、pull resistor、edge interrupt |
| Timer | Periodic、one-shot、PWM、input capture |
| DMA | Channel config、completion callback、scatter-gather |
| Watchdog | Init、refresh、triggered reset |

### QoR Metrics to Evaluate
- 全部 peripheral loopback test PASS
- DMA 数据和目标地址正确
- 不允许 infinite loop；所有 error path 都返回 timeout
- Error status 必须有实际含义

### Output Required
- 每个 peripheral 的 .c/.h
- Driver unit test suite
- Doxygen-compatible API 文档

---

## Stage: rtos_integration

### FreeRTOS Domain Rules
1. 为目标架构实现 `portmacro.h`。
2. 使用 hardware timer 产生 RTOS tick，默认 1 ms。
3. 实现 SVC、PendSV 或等价 context-switch handler。
4. Heap 默认使用 `heap_4.c`。
5. 用 `uxTaskGetStackHighWaterMark()` profile stack，再加 20% margin。
6. 开发阶段 `configCHECK_FOR_STACK_OVERFLOW=2`。
7. Priority inversion 使用支持 priority inheritance 的 mutex。

### RTOS-Aware Driver Rules
1. 用 semaphore pend 替代 busy-wait，由 ISR 在完成时 give semaphore。
2. 共享 peripheral 用 mutex，并记录最大 hold time。
3. DMA + RTOS 使用 event flag/semaphore 通知完成。
4. ISR 内禁止调用非 `FromISR` FreeRTOS API。

### QoR Metrics to Evaluate
- RTOS 成功 boot，idle task 运行，tick rate 正确
- 所有 task 成功创建、调度和运行
- 24 小时 stress test 无 stack overflow
- 并发访问 peripheral 时无 deadlock

### Output Required
- 自定义架构需要的 RTOS port layer
- 目标 `FreeRTOSConfig.h`
- Multi-task integration test

---

## Stage: driver_validation

### Validation Tiers
| Level | 测试 | 环境 |
|---|---|---|
| Unit | Peripheral loopback | Bare-metal on HW |
| Integration | Multi-peripheral DMA chain | RTOS on HW |
| System | 完整应用场景 | RTOS on HW |
| Stress | 24 小时高吞吐 | Overnight on HW |

### QoR Metrics to Evaluate
- 所有 peripheral driver test：100% PASS
- 24 小时 stress：0 failure
- 无 memory corruption，stack watermark 稳定
- Throughput 在理论最大值 10% 以内

### Output Required
- Test result report
- Performance measurement
- Known limitation 与 workaround

---

## Stage: system_integration

### Domain Rules
1. 所有 driver 先通过 unit validation。
2. 验证 UART + SPI + DMA + timer 等多 peripheral 并发。
3. 验证 sleep 进入/退出，并对每个 IRQ source 验证 wake-up。
4. 验证 warm/cold reset 后 peripheral 能完整重新初始化。
5. RAM 执行完整 walking-bit pattern test。

### QoR Metrics to Evaluate
- System scenario 与 golden reference 输出一致
- 1 小时系统运行无 lockup/unexpected reset
- Power mode current 与 spec 差异 ≤10%
- Warm/cold reset 后功能完全恢复

### Output Required
- System integration test report
- Power consumption measurement
- HW/SW 分类后的 bug list

---

## Stage: firmware_signoff

### Sign-off Checklist
- [ ] 全部 peripheral driver unit test 100% PASS
- [ ] RTOS 无 stack overflow/deadlock
- [ ] System integration PASS
- [ ] 24 小时 stress clean
- [ ] Power mode 已验证并实测
- [ ] Warm/cold reset 已验证
- [ ] P0/P1 bug 全关闭

### Output Required
- 已验证 firmware package
- Test result report
- Silicon team bring-up guide
- Known issues list

---

## Memory

### Write on stage completion
每个 stage 完成后按 `run_id` 在 `memory/firmware/experiences.jsonl`
写入/覆盖一条 JSON record。即使流程中断或单独调用 stage，也能持久化。
`run_id = firmware_<YYYYMMDD>_<HHMMSS>`，流程开始时生成一次并复用。
最终 sign-off 前保持 `signoff_achieved:false`。

### Run state
任何工具启动前第一步写 `memory/firmware/run_state.md`：
```markdown
run_id:      firmware_<YYYYMMDD>_<HHMMSS>
design_name: <design>
tool:        <primary tool>
start_time:  <ISO-8601>
last_stage:  <first stage name>
```
每个 stage 后更新 `last_stage`。文件/父目录不存在时创建。

### Optional: claude-mem index
如果存在 `mcp__plugin_ecc_memory__add_observations`，在写 experience 后把 applied fix
作为 observation 写入 `chip-design-firmware-fixes`；工具不存在时静默跳过。JSONL 是 canonical record。
