# 安装

请选择适合你当前环境的安装方式。对大多数用户来说，**方案 A（npm）** 最简单：无需 clone，也不需要 Python。

## 方案 A —— npm（推荐，无需 clone）

如果已经安装 Node.js（≥18），只需执行一条命令，无需 `git clone`，也无需 Python。未带参数时，安装器会**自动检测已安装的 AI 编程 Agent**（Claude Code、OpenAI Codex、OpenCode、Gemini、GitHub Copilot），显示检测结果及各自写入位置，确认后执行安装：

```bash
npx digital-chip-design-agents            # 检测已安装 Agent + 确认
npx digital-chip-design-agents --yes      # 检测并直接安装，不询问（适合 CI）
```

只要某个 Agent 的 CLI 位于 `PATH` 中，**或者**其配置目录存在（例如 `~/.claude`、`~/.codex`、`~/.config/opencode`、`~/.gemini`），就会被视为已安装。

对于 Claude Code，安装器会把全部插件复制到插件缓存并在 `settings.json` 中启用；对于其他工具，会生成相应的 context 文件（参见方案 D）。五类目标都由 Node 原生处理，不依赖 Python。

若要明确指定某个 Agent（或全部 Agent），可以跳过自动检测：

```bash
npx digital-chip-design-agents --ide claude     # 也可用 codex | opencode | gemini | copilot | all
npx digital-chip-design-agents --ide gemini --global
```

后续需要获取更新时重新运行对应命令即可。macOS、Linux、Windows 行为一致。单个 Node 进程会顺序复制插件，因此不会发生多个安装过程同时写插件缓存的问题。

## 方案 B —— 安装脚本

clone 仓库后运行一个脚本即可。与 npm 安装器相同，不带参数时会**自动检测已安装的 Agent**，确认后安装。若不希望交互确认，可在 `install.sh` 使用 `--yes` / `-y`，在 `install.ps1` 使用 `-Yes`。

Shell 安装脚本需要 `python3`；如果希望完全不依赖 Python，请使用方案 A。

**macOS / Linux / Git Bash：**

```bash
git clone https://github.com/chuanseng-ng/digital-chip-design-agents.git
cd digital-chip-design-agents
bash install.sh
```

**Windows（PowerShell）：**

```powershell
git clone https://github.com/chuanseng-ng/digital-chip-design-agents.git
cd digital-chip-design-agents
.\install.ps1
```

安装完成后重启 Claude Code，全部 17 个 Skill 和 16 个 Agent 将可用。

## 方案 C —— Marketplace（选择性安装）

如果只需要部分领域，可以通过 Claude Code Marketplace 单独安装。先注册 Marketplace，再安装需要的领域：

```text
/plugin marketplace add github:chuanseng-ng/digital-chip-design-agents
```

<details>
<summary>展开查看各插件安装命令</summary>

```text
/plugin install chip-design-architecture@digital-chip-design-agents
/plugin install chip-design-rtl@digital-chip-design-agents
/plugin install chip-design-verification@digital-chip-design-agents
/plugin install chip-design-formal@digital-chip-design-agents
/plugin install chip-design-synthesis@digital-chip-design-agents
/plugin install chip-design-dft@digital-chip-design-agents
/plugin install chip-design-sta@digital-chip-design-agents
/plugin install chip-design-hls@digital-chip-design-agents
/plugin install chip-design-pd@digital-chip-design-agents
/plugin install chip-design-soc@digital-chip-design-agents
/plugin install chip-design-memory-ip@digital-chip-design-agents
/plugin install chip-design-compiler@digital-chip-design-agents
/plugin install chip-design-firmware@digital-chip-design-agents
/plugin install chip-design-fpga@digital-chip-design-agents
```

</details>

## 方案 D —— 其他 AI 助手（Copilot / Gemini / OpenCode / Codex CLI）

方案 A 和 B 会自动检测这些工具，也可以显式安装到某个目标。npm 安装器（`npx digital-chip-design-agents --ide <target>`）和 shell 脚本都原生支持全部目标；请在你的芯片设计项目目录中使用 `--ide`：

```bash
# GitHub Copilot —— 在项目中创建 .github/instructions/
bash /path/to/digital-chip-design-agents/install.sh --ide copilot
# 可将生成的 .github/ 文件提交到版本库，与团队共享规则。

# Gemini Code Assist —— 在项目中创建 GEMINI.md；使用 --global 时创建 ~/GEMINI.md
bash /path/to/digital-chip-design-agents/install.sh --ide gemini

# OpenCode —— 在项目中创建 opencode.json；使用 /mode chip-<domain> 激活领域
bash /path/to/digital-chip-design-agents/install.sh --ide opencode

# OpenAI Codex CLI —— 在项目中创建 AGENTS.md；使用 --global 时创建 ~/.codex/instructions.md
bash /path/to/digital-chip-design-agents/install.sh --ide codex

# 同时安装到所有 IDE（也包括 Claude Code）
bash /path/to/digital-chip-design-agents/install.sh --ide all
```

**Windows（PowerShell）：** 将 `bash install.sh` 替换为 `.\install.ps1`，将 `--ide` 替换为 `-IDE`。

领域知识会直接从插件源文件加载，不复制冗余内容。今后重新运行安装命令即可获取更新。

## 使用方式 —— 用自然语言描述任务

```
为我的 AXI DMA 控制器模块运行 RTL 设计流程
分析 routed DEF 中的时序违例并给出 ECO 建议
为已完成 DFT 插入的网表生成 ATPG pattern
为 FIFO 模块构建 UVM testbench
```

Claude 会在执行前自动加载正确的 Skill。
