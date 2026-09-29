# 嵌入式固件与设备驱动开发流程
## Orchestrator + Stage Agents + Skills

> **目的**：面向芯片固件与设备驱动开发的 AI 驱动流程。覆盖 BSP 开发、外设驱动、RTOS 集成和固件验证。

---

## 1. 共享状态对象

```json
{
  "run_id": "firmware_001",
  "chip_name": "my_soc",
  "inputs": {
    "chip_datasheet":    "path/to/datasheet.pdf",
    "memory_map":        "path/to/memory_map.md",
    "peripheral_list":   ["UART", "SPI", "I2C", "GPIO", "DMA", "Timer", "Ethernet"],
    "rtos":              "FreeRTOS | Zephyr | bare-metal",
    "toolchain":         "arm-none-eabi-gcc | custom_toolchain",
    "target_hw":         "FPGA_prototype | Silicon",
    "language":          "C | C++"
  },
  "stages": {
    "bsp_development":    { "status": "pending", "output": {} },
    "peripheral_drivers": { "status": "pending", "output": {} },
    "rtos_integration":   { "status": "pending", "output": {} },
    "driver_validation":  { "status": "pending", "output": {} },
    "system_integration": { "status": "pending", "output": {} },
    "firmware_signoff":   { "status": "pending", "output": {} }
  },
  "drivers_complete": [],
  "test_results": {},
  "flow_status": "not_started"
}
```

---

## 2. Stage Sequence（阶段顺序）

```
[BSP Development] ──► [Peripheral Drivers] ──► [RTOS Integration]
                              ▲                        │ driver bugs
                              └────────────────────────┘
                                                       │ pass
                              ▼
                       [Driver Validation] ──► [System Integration]
                                                       │ system test fail
                                                       └──► Peripheral Drivers
                                                       │ pass
                                               [Firmware Sign-off]
```

---

## 3. Skill 文件说明

### 3.1 `sv-fw-bsp/SKILL.md`

```markdown
# Skill: Firmware — Board Support Package (BSP) Development

## Purpose
创建从 reset 开始完成芯片启动和初始化所需的硬件抽象层。

## BSP Components
1. Startup code（crt0.S / startup.c）：
   - 设置 stack pointer
   - 初始化 .data（从 flash 复制到 RAM）
   - 清零 .bss
   - 调用 SystemInit()
   - 跳转 main()

2. System initialization（SystemInit）：
   - 配置 PLL / clock tree
   - 配置 memory（flash wait state、DRAM init）
   - 若启动阶段允许，关闭 watchdog
   - 如存在 I-cache / D-cache，完成 cache enable

3. Interrupt controller（NVIC / PLIC / custom）：
   - 定义 vector table
   - IRQ enable/disable primitive
   - Priority configuration API
   - ISR registration mechanism

4. Memory map header（memory_map.h）：
   - 全部 peripheral base address 的 #define
   - Register offset definition
   - Bit field definition（优先 struct/union 或 mask）

5. Linker script：
   - Boot region、code region、data region、stack、heap

## Coding Standards for BSP
1. Volatile：所有硬件寄存器访问必须使用 volatile pointer
2. Atomic：硬件寄存器 read-modify-write 时关闭 IRQ 或使用 atomic op
3. Barriers：硬件访问序列前后使用 memory barrier（DMB/DSB）
4. BSP 不调用 OS API：必须保持 RTOS 无关

## QoR Metrics
- Boot：芯片在预期时间进入 main()
- Clock：所有 PLL lock，peripheral clock 正确
- Interrupt：vector table 有效，default handler 已配置
- Memory：.data 和 .bss 正确初始化

## Output Required
- startup.S 和 system_init.c
- memory_map.h（完整寄存器定义）
- Linker script
- BSP build system（Makefile 或 CMakeLists.txt）
```

---

### 3.2 `sv-fw-drivers/SKILL.md`

```markdown
# Skill: Firmware — Peripheral Driver Development

## Purpose
为芯片全部外设实现结构清晰、可测试、可复用的设备驱动。

## Driver Architecture Pattern (HAL-style)
```c
// Initialization
status_t UART_Init(UART_Type *base, const uart_config_t *config);

// Data transfer (polling)
status_t UART_WriteBlocking(UART_Type *base, const uint8_t *data, size_t len);
status_t UART_ReadBlocking(UART_Type *base, uint8_t *data, size_t len);

// Data transfer (interrupt-driven)
status_t UART_TransferSendNonBlocking(UART_Type *base, uart_handle_t *handle,
                                       uart_transfer_t *xfer);

// ISR (called from vector table)
void UART_TransferHandleIRQ(UART_Type *base, uart_handle_t *handle);
```

## Driver Development Rules
1. 所有 register access 都通过 memory_map.h，禁止 magic number
2. 所有 polling loop 必须有 timeout，超时返回 error
3. 返回 status code，不使用无意义的 void；统一定义 status_t enum
4. 记录 driver 是否 thread-safe；不安全时明确 lock requirement
5. 高带宽外设提供 DMA-based transfer variant
6. Low-power mode 提供 suspend/resume hook
7. Async completion 使用 callback

## Driver Test Pattern (bare-metal)
- Loopback：UART TX→RX、SPI master→slave
- DMA：传输后核对 buffer contents
- Interrupt：确认正确事件触发 callback
- Error injection：强制错误并验证处理

## Standard Peripheral Driver Checklist
- [ ] UART：init、send、receive、baud rate、parity、flow control
- [ ] SPI：master/slave、全部 mode（CPOL/CPHA）、DMA
- [ ] I2C：master/slave、7/10-bit addressing、repeated start
- [ ] GPIO：input/output、pull up/down、edge interrupt
- [ ] Timer：periodic、one-shot、PWM、input capture
- [ ] DMA：channel config、scatter-gather、completion callback
- [ ] Watchdog：init、refresh、triggered reset test
- [ ] Ethernet：MAC init、DMA descriptor、PHY init（MDIO）

## Output Required
- 每个 peripheral 一组 .c/.h
- Driver test suite
- Doxygen-compatible API 文档
```

---

### 3.3 `sv-fw-rtos/SKILL.md`

```markdown
# Skill: Firmware — RTOS Integration

## Purpose
将 FreeRTOS、Zephyr 或类似 RTOS 与 BSP、peripheral driver 集成，
支持多任务 firmware。

## FreeRTOS Integration Steps
1. Port layer：为目标架构实现 portmacro.h
2. Tick timer：用 hardware timer 提供 RTOS tick（通常 1 ms）
3. Context switch：实现 PendSV/SVC 或等价 handler
4. Heap：常见嵌入式场景默认选 heap_4
5. Stack sizing：用 uxTaskGetStackHighWaterMark 评估
6. Interrupt nesting：配置 BASEPRI 或等价 IRQ masking
7. Priority inversion：使用支持 priority inheritance 的 mutex

## RTOS-Aware Driver Requirements
1. Blocking call：使用 semaphore/queue，避免 busy-wait
2. ISR→task notification：使用 xSemaphoreGiveFromISR() 模式
3. Mutual exclusion：共享外设使用 mutex
4. DMA + RTOS：用 event flag/semaphore 通知完成
5. ISR 内禁止调用非 FromISR 版本 FreeRTOS API

## Common RTOS Integration Bugs
- Stack overflow：设置 configCHECK_FOR_STACK_OVERFLOW = 2
- Priority inversion：使用带 priority inheritance 的 mutex
- ISR 调用非 ISR API：debug build 中通过 assert/linker 捕获
- Tick frequency 错误：用 logic analyzer 测量确认

## QoR Metrics
- RTOS 能正常启动：idle task 运行，tick 频率正确
- 所有 application task 成功创建并运行
- Stress test 无 stack overflow
- Driver + RTOS 并发访问无 deadlock

## Output Required
- RTOS port layer（自定义 target 时）
- FreeRTOSConfig.h / prj.conf
- Multi-task producer-consumer integration test
```

---

### 3.4 `sv-fw-validation/SKILL.md`

```markdown
# Skill: Firmware — Validation and System Testing

## Purpose
验证 firmware 能正确控制全部外设并满足系统级功能要求。

## Validation Strategy
| Level | 测试内容 | 环境 |
|---|---|---|
| Unit (driver) | 单个外设、loopback | Bare-metal on HW |
| Integration | 多外设协同 | RTOS on HW |
| System | 完整 application scenario | RTOS on HW |
| Stress | 长时间、高吞吐、corner case | Overnight on HW |
| Power | Low-power mode / wake-up | HW + power meter |

## Automated Testing Framework
1. Unity 或 CppUTest：C unit-test framework
2. Python host script 通过 UART/JTAG 控制 target
3. Target 通过 UART 回报 PASS/FAIL，host 记录结果
4. 每次 commit 可通过 FPGA farm/emulator 接入 CI

## Performance Validation
- UART：maximum baud rate throughput
- SPI：maximum clock throughput
- DMA：对比理论 transfer rate
- Interrupt latency：测量 IRQ 到 ISR entry 时间

## QoR Metrics
- 所有 peripheral driver test 100% PASS
- System integration test 100% PASS
- 24h stress test 0 failure
- Performance 与理论上限差异 ≤10%

## Output Required
- Per-peripheral / per-scenario test report
- Performance measurement
- Known limitation 与 workaround
```

---

## 4. Orchestrator System Prompt

```
You are the Firmware Development Orchestrator.

You guide the development and validation of embedded firmware
for a custom chip, from BSP through system integration testing.

STAGE SEQUENCE:
  bsp_development → peripheral_drivers → rtos_integration →
  driver_validation → system_integration → firmware_signoff

LOOP-BACK RULES:
  - peripheral_drivers: driver test fail    → peripheral_drivers (max 3x)
  - rtos_integration: deadlock/overflow     → rtos_integration (max 3x)
  - driver_validation: fail                 → peripheral_drivers (max 3x)
  - system_integration: fail                → peripheral_drivers (max 2x)

Track drivers_complete[] in state_object.
Do not proceed to rtos_integration until all drivers have passed unit tests.
Output: Validated firmware package ready for application development.
```

> 上述 System Prompt 中的 stage 名、字段名和固定枚举属于机器接口，因此保留英文；其含义已在本文正文中中文化。
