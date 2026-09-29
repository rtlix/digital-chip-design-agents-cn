# Firmware Domain Knowledge（固件领域知识）

## Known Failure Patterns

- **QEMU peripheral emulation gap**：会导致 `bsp_development` 假失败。若 QEMU 上 BSP test 失败但 register map 正确，先用 `qemu-system-arm -machine help` 确认 peripheral 是否被实现；未实现的外设应由 RTL sim 或 FPGA bring-up 验证。
- **FreeRTOS stack overflow 的静默破坏**：不启用 `configCHECK_FOR_STACK_OVERFLOW=2` 时，stack overflow 可能静默覆盖相邻 task stack，形成随机 crash。开发阶段始终开启 `configCHECK_FOR_STACK_OVERFLOW=2` 和 `configUSE_MALLOC_FAILED_HOOK=1`。
- **Bare-metal clock tree validation**：验证 clock tree 前初始化 peripheral 会造成难以复现的间歇失败。`bsp_development` 中应先确认 PLL lock 和 clock divider，再初始化任何 peripheral。

## Successful Tool Flags

- `arm-none-eabi-gcc -fstack-usage`：生成每个 function 的 `.su` stack-usage 文件，可用于设置 FreeRTOS task stack 前计算 worst-case depth。
- `openocd -f interface/<probe>.cfg -f target/<mcu>.cfg -c "program <elf> verify reset exit"`：一次完成 flash/program/verify；`verify` 可捕获静默 image corruption。
- `riscv64-unknown-elf-objdump -d --visualize-jumps`：bring-up 时用于发现 startup code 中异常 branch。

## PDK / Tool Quirks

- **J-Link RTT buffer**：bring-up logging 建议把 `SEGGER_RTT_BUFFER_SIZE_UP` 提高到至少 4096；默认 1024 在高吞吐日志下容易丢数据。
- **TRACE32 JTAG speed**：早期 bring-up 在 power delivery 验证前，把 JTAG clock 降到 ≤1 MHz；边缘电源条件下较高 JTAG speed 更易出现 corruption。

## Notes

- `stress_test_24h_clean` 是 sign-off gate，必须在 target hardware 上跑。QEMU 24h PASS 不能替代真实硬件验证。
