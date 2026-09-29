# install.ps1 - 安装 digital-chip-design-agents 插件
#
# 用法：
#   .\install.ps1                           # auto-detect installed agents + confirm
#   .\install.ps1 -Yes                      # auto-detect, no confirmation prompt
#   .\install.ps1 -IDE claude               # Claude Code (explicit)
#   .\install.ps1 -IDE copilot              # GitHub Copilot (.github\ in cwd)
#   .\install.ps1 -IDE gemini               # Gemini Code Assist (GEMINI.md in cwd)
#   .\install.ps1 -IDE gemini -Global       # Gemini global (~\GEMINI.md)
#   .\install.ps1 -IDE opencode             # OpenCode (opencode.json in cwd)
#   .\install.ps1 -IDE opencode -Global     # OpenCode global (~\.config\opencode\)
#   .\install.ps1 -IDE codex                # OpenAI Codex CLI (AGENTS.md in cwd)
#   .\install.ps1 -IDE codex -Global        # OpenAI Codex CLI global (~\.codex\instructions.md)
#   .\install.ps1 -IDE all                  # Claude Code + all four other IDEs (copilot, gemini, opencode, codex)
#
# 不指定 -IDE 时，脚本会检测五种受支持的 Agent
#（claude、codex、opencode、gemini、copilot），确认后安装到检测到的目标。
# 显式指定 -IDE 会跳过自动检测。
#
#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet("","auto","claude","copilot","gemini","opencode","codex","all")]
    [string]$IDE = "",
    [switch]$Global,
    [switch]$Yes
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoDir     = $PSScriptRoot
$Marketplace = "digital-chip-design-agents"
# Each plugin's cache version is read from its own .claude-plugin\plugin.json
# below, so plugins at different versions land in the correct path.
# python3 is located lazily below — only the non-Claude generators need it.
$Python = "python3"

# ── Shared sanity checks ──────────────────────────────────────────────────────
if (-not (Test-Path (Join-Path $RepoDir ".claude-plugin\marketplace.json"))) {
    Write-Error "找不到仓库根目录。请确认 install.ps1 位于已克隆的仓库内。"
    exit 1
}

# ── Plugin list & mapping ─────────────────────────────────────────────────────
$Plugins = @(
    "chip-design-architecture",  "chip-design-rtl",
    "chip-design-verification",  "chip-design-formal",
    "chip-design-synthesis",     "chip-design-dft",
    "chip-design-sta",           "chip-design-hls",
    "chip-design-pd",            "chip-design-soc",
    "chip-design-memory-ip",
    "chip-design-compiler",      "chip-design-firmware",
    "chip-design-fpga",          "chip-design-infrastructure",
    "chip-design-meta"
)

$PluginDirs = @{
    "chip-design-architecture" = "architecture"
    "chip-design-rtl"          = "rtl-design"
    "chip-design-verification" = "verification"
    "chip-design-formal"       = "formal"
    "chip-design-synthesis"    = "synthesis"
    "chip-design-dft"          = "dft"
    "chip-design-sta"          = "sta"
    "chip-design-hls"          = "hls"
    "chip-design-pd"           = "pd"
    "chip-design-soc"          = "soc"
    "chip-design-memory-ip"    = "memory-ip"
    "chip-design-compiler"     = "compiler"
    "chip-design-firmware"       = "firmware"
    "chip-design-fpga"           = "fpga"
    "chip-design-infrastructure" = "infrastructure"
    "chip-design-meta"           = "meta"
}

# Helper: run a Python script stored in a temp file, then clean up
function Invoke-PythonScript {
    param([string]$ScriptContent, [string[]]$Args = @())
    $tmp = [System.IO.Path]::GetTempFileName() + ".py"
    try {
        $ScriptContent | Set-Content $tmp -Encoding UTF8
        & $Python $tmp @Args
        if ($LASTEXITCODE -ne 0) { throw "Python 脚本执行失败（退出码 $LASTEXITCODE）" }
    } finally {
        if (Test-Path $tmp) { Remove-Item $tmp -Force }
    }
}

# ── Detection (read-only) ─────────────────────────────────────────────────────
# A target counts as installed if its CLI is on PATH or its config dir exists.
# Mirrors bin\detect.mjs. Copilot is project-scoped, so it is detected only via
# the gh / copilot CLI.
function Test-AgentInstalled {
    param([string]$Id)
    switch ($Id) {
        "claude" {
            if (Get-Command claude -ErrorAction SilentlyContinue) { return $true }
            $cdir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE ".claude" }
            return (Test-Path $cdir)
        }
        "codex" {
            if (Get-Command codex -ErrorAction SilentlyContinue) { return $true }
            return (Test-Path (Join-Path $env:USERPROFILE ".codex"))
        }
        "opencode" {
            if (Get-Command opencode -ErrorAction SilentlyContinue) { return $true }
            return (Test-Path (Join-Path $env:USERPROFILE ".config\opencode"))
        }
        "gemini" {
            if (Get-Command gemini -ErrorAction SilentlyContinue) { return $true }
            return (Test-Path (Join-Path $env:USERPROFILE ".gemini"))
        }
        "copilot" {
            if (Get-Command copilot -ErrorAction SilentlyContinue) { return $true }
            return [bool](Get-Command gh -ErrorAction SilentlyContinue)
        }
    }
    return $false
}

# Where each target writes, so the confirmation shows repo vs $HOME vs config dir.
# Mirrors bin/detect.mjs and the per-IDE install blocks below.
function Get-AgentDestination {
    param([string]$Id)
    switch ($Id) {
        "claude" {
            $cdir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE ".claude" }
            return "$cdir（全局插件缓存）"
        }
        "codex"    { if ($Global) { return (Join-Path $env:USERPROFILE ".codex\instructions.md") } else { return (Join-Path (Get-Location).Path "AGENTS.md") } }
        "opencode" { if ($Global) { return (Join-Path $env:USERPROFILE ".config\opencode\config.json") } else { return (Join-Path (Get-Location).Path "opencode.json") } }
        "gemini"   { if ($Global) { return (Join-Path $env:USERPROFILE "GEMINI.md") } else { return (Join-Path (Get-Location).Path "GEMINI.md") } }
        "copilot"  { return (Join-Path (Get-Location).Path ".github") }
    }
    return ""
}

# ── Build the selection set ───────────────────────────────────────────────────
$AllTargets = @("claude","codex","opencode","gemini","copilot")
$Sel = @{}

if ([string]::IsNullOrEmpty($IDE) -or $IDE -eq "auto") {
    Write-Host "正在检测已安装的 AI 编码 Agent..."
    Write-Host ""
    $detected = @()
    foreach ($t in $AllTargets) {
        if (Test-AgentInstalled $t) { $detected += $t; Write-Host "  [找到] $t -> $(Get-AgentDestination $t)" }
        else { Write-Host "  [  -  ] $t" }
    }
    if ($detected.Count -eq 0) {
        Write-Host ""
        Write-Host "未检测到受支持的 Agent。可以显式指定一个目标安装："
        Write-Host "  .\install.ps1 -IDE claude   (or copilot|gemini|opencode|codex|all)"
        exit 0
    }
    $doPrompt = (-not $Yes) -and (-not [Console]::IsInputRedirected)
    if ($doPrompt) {
        Write-Host ""
        $ans = (Read-Host '安装到所有已检测到的目标吗？[Y/n]（也可以输入子集，例如 "claude,codex"）').Trim().ToLower()
        if ($ans -eq "" -or $ans -eq "y" -or $ans -eq "yes") {
            foreach ($t in $detected) { $Sel[$t] = $true }
        } elseif ($ans -eq "n" -or $ans -eq "no") {
            Write-Host "已取消。"; exit 0
        } else {
            foreach ($p in ($ans -split ",")) {
                $p = $p.Trim()
                if ($detected -contains $p) { $Sel[$p] = $true }
            }
        }
    } else {
        foreach ($t in $detected) { $Sel[$t] = $true }
        Write-Host ""
        Write-Host "将安装到所有检测到的目标。"
    }
} elseif ($IDE -eq "all") {
    foreach ($t in $AllTargets) { $Sel[$t] = $true }
} else {
    $Sel[$IDE] = $true
}

if ($Sel.Count -eq 0) { Write-Host "未选择任何目标，已取消。"; exit 0 }

# ── python3 is required for every target in the shell installer ───────────────
# (Even the Claude block reads plugin versions and merges settings.json via
# Python.) The Python-free path is the npm installer: npx digital-chip-design-agents.
if (-not (Get-Command python3 -ErrorAction SilentlyContinue)) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $Python = "python"
    } else {
        Write-Error "install.ps1 需要 python3（或 python），但 PATH 中未找到。如需无需 Python 的安装方式，请使用：npx digital-chip-design-agents"
        exit 1
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code install
# ═══════════════════════════════════════════════════════════════════════════════
if ($Sel.ContainsKey("claude")) {

    $ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR }
                 else { Join-Path $env:USERPROFILE ".claude" }

    $CacheDir  = Join-Path $ClaudeDir "plugins\cache\$Marketplace"
    $Settings  = Join-Path $ClaudeDir "settings.json"

    Write-Host "Claude 配置目录 : $ClaudeDir"
    Write-Host "插件缓存目录   : $CacheDir"
    Write-Host ""

    if (-not (Test-Path $ClaudeDir)) {
        Write-Error "在 '$ClaudeDir' 找不到 Claude 配置目录。`n请确认已安装 Claude Code，并且至少运行过一次。"
        exit 1
    }

    Write-Host "正在安装 Claude Code 插件缓存..."
    foreach ($Plugin in $Plugins) {
        $Subdir = $PluginDirs[$Plugin]
        $Src    = Join-Path $RepoDir "plugins\$Subdir"
        $PluginJson = Join-Path $Src ".claude-plugin\plugin.json"
        $Version = & $Python -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" $PluginJson
        if ($LASTEXITCODE -ne 0) { throw "无法从 $PluginJson 读取版本号" }
        $Dest   = Join-Path $CacheDir "$Plugin\$Version"

        if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
        New-Item -ItemType Directory -Path $Dest -Force | Out-Null

        Copy-Item (Join-Path $Src "agents")         $Dest -Recurse -Force
        Copy-Item (Join-Path $Src "skills")         $Dest -Recurse -Force
        Copy-Item (Join-Path $Src ".claude-plugin") $Dest -Recurse -Force

        $Readme  = Join-Path $RepoDir "README.md"
        if (Test-Path $Readme)  { Copy-Item $Readme  $Dest -Force }
        $License = Join-Path $RepoDir "LICENSE"
        if (Test-Path $License) { Copy-Item $License $Dest -Force }

        Write-Host "  [OK] $Plugin"
    }

    Write-Host ""
    Write-Host "正在更新 $Settings ..."

    $SettingsPy = @'
import json, sys, os

settings_path = sys.argv[1]
marketplace   = sys.argv[2]

plugins = [
  "chip-design-architecture", "chip-design-rtl", "chip-design-verification",
  "chip-design-formal",       "chip-design-synthesis", "chip-design-dft",
  "chip-design-sta",          "chip-design-hls",       "chip-design-pd",
  "chip-design-soc",          "chip-design-compiler",  "chip-design-firmware",
  "chip-design-fpga",         "chip-design-infrastructure",
  "chip-design-memory-ip",    "chip-design-meta",
]

cfg = {}
if os.path.exists(settings_path):
    with open(settings_path) as f:
        cfg = json.load(f)

enabled = cfg.setdefault("enabledPlugins", {})
for p in plugins:
    enabled[f"{p}@{marketplace}"] = True

mp = cfg.setdefault("extraKnownMarketplaces", {})
mp[marketplace] = {
    "source": {"source": "directory", "path": sys.argv[3]}
}

with open(settings_path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")

print(f"  [OK] settings.json 中已启用 {len(plugins)} 个插件")
'@
    Invoke-PythonScript -ScriptContent $SettingsPy -Args @($Settings, $Marketplace, $RepoDir)

    Write-Host ""
    Write-Host "完成！请重启 Claude Code，以激活全部 16 个插件。"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GitHub Copilot install
# ═══════════════════════════════════════════════════════════════════════════════
if ($Sel.ContainsKey("copilot")) {

    Write-Host ""
    Write-Host "正在安装 GitHub Copilot 指令文件..."

    $TargetDir = (Get-Location).Path

    $CopilotPy = @'
import json, os, re, glob, sys, shutil

repo_dir   = sys.argv[1]
target_dir = sys.argv[2]

applyto_map = json.load(open(os.path.join(repo_dir, 'ides', 'copilot', 'applyto-map.json')))

gh_dir = os.path.join(target_dir, '.github', 'instructions')
os.makedirs(gh_dir, exist_ok=True)
shutil.copy(
    os.path.join(repo_dir, 'ides', 'copilot', '.github', 'copilot-instructions.md'),
    os.path.join(target_dir, '.github', 'copilot-instructions.md'),
)

skill_files = sorted(glob.glob(os.path.join(repo_dir, 'plugins', '*', 'skills', '*', 'SKILL.md')))
for skill_path in skill_files:
    parts  = os.path.normpath(skill_path).split(os.sep)
    domain = parts[parts.index('plugins') + 1]

    applyto = applyto_map.get(domain, '**/*')
    content = open(skill_path, encoding='utf-8').read()
    body    = re.sub(r'^---\n.*?\n---\n', '', content, count=1, flags=re.DOTALL).strip()

    out_path = os.path.join(gh_dir, domain + '.instructions.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('---\napplyTo: "' + applyto + '"\n---\n\n' + body + '\n')
    print('  [OK] .github/instructions/' + domain + '.instructions.md')

print('\nCopilot：已安装 ' + str(len(skill_files)) + ' 个指令文件。')
print('如需与团队共享这些领域规则，请提交 .github/ 目录。')
'@
    Invoke-PythonScript -ScriptContent $CopilotPy -Args @($RepoDir, $TargetDir)
}

# ═══════════════════════════════════════════════════════════════════════════════
# Gemini Code Assist install
# ═══════════════════════════════════════════════════════════════════════════════
if ($Sel.ContainsKey("gemini")) {

    Write-Host ""
    Write-Host "正在安装 Gemini Code Assist 上下文文件..."

    $GeminiTarget = if ($Global) {
        Join-Path $env:USERPROFILE "GEMINI.md"
    } else {
        Join-Path (Get-Location).Path "GEMINI.md"
    }

    $GeminiPy = @'
import os, glob, sys

repo_dir = sys.argv[1]
out_path = sys.argv[2]

header = open(os.path.join(repo_dir, 'ides', 'gemini', 'gemini-header.md'), encoding='utf-8').read().strip()

lines = [
    '# 数字芯片设计 Agents --- Gemini 上下文',
    '<!-- 由 install.ps1 -IDE gemini 生成 -->',
    '<!-- Source: ' + repo_dir + ' -->',
    '',
    header,
    '',
    '## 领域知识',
    '',
]

skill_files = sorted(glob.glob(os.path.join(repo_dir, 'plugins', '*', 'skills', '*', 'SKILL.md')))
agent_map   = {
    os.path.basename(os.path.dirname(os.path.dirname(p))): p
    for p in glob.glob(os.path.join(repo_dir, 'plugins', '*', 'agents', '*.md'))
}

for skill_path in skill_files:
    parts  = os.path.normpath(skill_path).split(os.sep)
    domain = parts[parts.index('plugins') + 1]
    lines.append('### ' + domain)
    lines.append('')
    lines.append('@' + skill_path)
    if domain in agent_map:
        lines.append('@' + agent_map[domain])
    lines.append('')

with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print('  [OK] ' + out_path)
print('  (' + str(len(skill_files)) + ' domains, ' + str(len(skill_files) + len(agent_map)) + ' @-imports)')
'@
    Invoke-PythonScript -ScriptContent $GeminiPy -Args @($RepoDir, $GeminiTarget)
}

# ═══════════════════════════════════════════════════════════════════════════════
# OpenCode install
# ═══════════════════════════════════════════════════════════════════════════════
if ($Sel.ContainsKey("opencode")) {

    Write-Host ""
    Write-Host "正在安装 OpenCode 配置..."

    $OpenCodeTarget = if ($Global) {
        Join-Path $env:USERPROFILE ".config\opencode\config.json"
    } else {
        Join-Path (Get-Location).Path "opencode.json"
    }

    $IsGlobalStr = if ($Global) { "true" } else { "false" }

    $OpenCodePy = @'
import json, os, glob, re, sys

repo_dir  = sys.argv[1]
target    = sys.argv[2]
is_global = sys.argv[3] == 'true'

mode_display = {
    'architecture': ('chip-architecture', '芯片架构评估'),
    'rtl-design':   ('chip-rtl',          'RTL 设计（SystemVerilog）'),
    'verification': ('chip-verification', '功能验证（UVM）'),
    'formal':       ('chip-formal',       '形式验证（FPV/LEC）'),
    'synthesis':    ('chip-synthesis',    '逻辑综合'),
    'dft':          ('chip-dft',          '可测性设计（DFT）'),
    'sta':          ('chip-sta',          '静态时序分析（STA）'),
    'hls':          ('chip-hls',          '高层综合（HLS）'),
    'pd':           ('chip-pd',           '物理设计（PD）'),
    'soc':          ('chip-soc',          'SoC IP 集成'),
    'memory-ip':    ('chip-memory-ip',    'Memory IP 设计'),
    'compiler':     ('chip-compiler',     '编译器工具链'),
    'firmware':     ('chip-firmware',     '嵌入式固件'),
    'fpga':         ('chip-fpga',         'FPGA 原型验证'),
}

base = json.load(open(os.path.join(repo_dir, 'ides', 'opencode', 'opencode-base.json')))
modes = {}

agent_files = sorted(glob.glob(os.path.join(repo_dir, 'plugins', '*', 'agents', '*.md')))
for agent_path in agent_files:
    parts  = os.path.normpath(agent_path).split(os.sep)
    domain = parts[parts.index('plugins') + 1]

    content = open(agent_path, encoding='utf-8').read()
    m = re.search(r'^description:\s*>?\s*\n((?:  .+\n)+)', content, re.MULTILINE)
    desc = ' '.join(l.strip() for l in m.group(1).strip().splitlines()) if m else domain
    desc = desc[:120]

    mode_key, mode_name = mode_display.get(domain, ('chip-' + domain, domain.replace('-', ' ').title()))
    prompt_path = agent_path if os.path.isabs(agent_path) else os.path.relpath(agent_path, os.path.dirname(target))
    modes[mode_key] = {'name': mode_name, 'description': desc, 'model': base.get('model', 'anthropic/claude-sonnet-4-5'), 'prompt': '{file:' + prompt_path + '}'}

if is_global and os.path.exists(target):
    existing = json.load(open(target))
    existing.setdefault('mode', {}).update(modes)
    out = existing
else:
    base['mode'] = modes
    out = base
    if is_global:
        os.makedirs(os.path.dirname(target), exist_ok=True)

with open(target, 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)
    f.write('\n')

print('  [OK] ' + target + ' --- ' + str(len(modes)) + ' modes')
print('  在 OpenCode 中使用 /mode chip-<domain> 激活对应领域。')
'@
    Invoke-PythonScript -ScriptContent $OpenCodePy -Args @($RepoDir, $OpenCodeTarget, $IsGlobalStr)
}

# ═══════════════════════════════════════════════════════════════════════════════
# OpenAI Codex CLI install
# ═══════════════════════════════════════════════════════════════════════════════
if ($Sel.ContainsKey("codex")) {

    Write-Host ""
    Write-Host "正在安装 OpenAI Codex CLI 上下文文件..."

    $CodexTarget = if ($Global) {
        Join-Path $env:USERPROFILE ".codex\instructions.md"
    } else {
        Join-Path (Get-Location).Path "AGENTS.md"
    }

    $CodexPy = @'
import os, glob, re, sys

repo_dir = sys.argv[1]
out_path = sys.argv[2]

header = open(os.path.join(repo_dir, 'ides', 'codex', 'AGENTS.md'), encoding='utf-8').read().strip()

lines = [
    '# 数字芯片设计 Agents --- Codex CLI 上下文',
    '<!-- 由 install.ps1 -IDE codex 生成 -->',
    '<!-- Source: ' + repo_dir + ' -->',
    '',
    header,
    '',
    '## 领域知识',
    '',
]

skill_files = sorted(glob.glob(os.path.join(repo_dir, 'plugins', '*', 'skills', '*', 'SKILL.md')))

for skill_path in skill_files:
    parts  = os.path.normpath(skill_path).split(os.sep)
    domain = parts[parts.index('plugins') + 1]

    content = open(skill_path, encoding='utf-8').read()
    body    = re.sub(r'^---\n.*?\n---\n', '', content, count=1, flags=re.DOTALL).strip()

    lines.append('### ' + domain)
    lines.append('')
    lines.append(body)
    lines.append('')

parent = os.path.dirname(out_path)
if parent:
    os.makedirs(parent, exist_ok=True)

with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print('  [OK] ' + out_path)
print('  （已内联 ' + str(len(skill_files)) + ' 个领域）')
'@
    Invoke-PythonScript -ScriptContent $CodexPy -Args @($RepoDir, $CodexTarget)
}
