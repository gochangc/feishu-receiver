# 飞书消息接收服务 - PowerShell 安装脚本
# 用法: irm https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.ps1 | iex

$ErrorActionPreference = 'Stop'

$InstallDir = "$env:LOCALAPPDATA\feishu-receiver"
$LogDir = "$InstallDir\logs"
$RepoUrl = 'https://github.com/gochangc/feishu-receiver.git'

if ($env:FEISHU_RECEIVER_WORKDIR) {
    $WorkDir = $env:FEISHU_RECEIVER_WORKDIR
} else {
    $WorkDir = "$env:USERPROFILE\workspace"
}

Write-Host '==> 检查依赖...' -ForegroundColor Cyan
foreach ($cmd in @('python3', 'lark-cli', 'claude')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  错误: $cmd 未找到" -ForegroundColor Red
        exit 1
    }
}
Write-Host '  依赖检查通过'

Write-Host '==> 检查 lark-cli 配置...'
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'SilentlyContinue'
$larkStatus = lark-cli auth status 2>&1 | Out-String
$ErrorActionPreference = $prevEAP
if ($larkStatus -match 'not configured') {
    Write-Host '  警告: lark-cli 尚未配置' -ForegroundColor Yellow
    Write-Host '  请执行: lark-cli config init --app-id <AppID> --app-secret-stdin --brand feishu'
} else {
    Write-Host '  lark-cli 已配置'
}

Write-Host '==> 下载项目文件...'
if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
}
git clone --depth 1 $RepoUrl $InstallDir *>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '  克隆失败，请检查网络' -ForegroundColor Red
    exit 1
}
Remove-Item -Recurse -Force "$InstallDir\.git" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $LogDir *>$null

Write-Host '==> 创建命令入口...'
Copy-Item "$InstallDir\bin\feishu-receiver.bat" "$InstallDir\feishu-receiver.bat"

Write-Host '==> 添加 PATH...'
$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
if ($userPath -notlike "*$InstallDir*") {
    if ($userPath) {
        $newPath = $userPath + ';' + $InstallDir
    } else {
        $newPath = $InstallDir
    }
    setx PATH $newPath *>$null
    Write-Host '  已添加到用户 PATH'
} else {
    Write-Host '  已在 PATH 中'
}

Write-Host ''
Write-Host '========================================' -ForegroundColor Green
Write-Host '安装完成！' -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Green
Write-Host "安装目录: $InstallDir"
Write-Host "日志目录: $LogDir"
Write-Host "工作目录: $WorkDir"
Write-Host ''
Write-Host '启动: feishu-receiver <start|stop|status|restart|foreground>'
Write-Host "日志: Get-Content $LogDir\feishu-receiver.log -Wait"
Write-Host "卸载: 删除 $InstallDir 即可"
Write-Host '========================================' -ForegroundColor Green