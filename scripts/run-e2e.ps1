# CI 用：运行安装程序，实时输出日志；超时则结束进程并导出诊断信息。
param(
    [Parameter(Mandatory)] [string]$Exe,
    [Parameter(Mandatory)] [string]$Mode,
    [switch]$Duplex,
    [int]$TimeoutSec = 480
)
$log = Join-Path (Get-Location) 'e2e.log'
Remove-Item $log -ErrorAction SilentlyContinue
$args = @('--cli', '--mode', $Mode, '--ip', '127.0.0.1', '--port', '50081', '--test-page', '--log-file', $log)
if ($Duplex) { $args += '--duplex' }
$p = Start-Process $Exe -ArgumentList $args -PassThru
$pos = 0
$sw = [Diagnostics.Stopwatch]::StartNew()
function Flush-Log {
    if (Test-Path $log) {
        $lines = @(Get-Content $log -Encoding UTF8)
        if ($lines.Count -gt $script:pos) { $lines[$script:pos..($lines.Count - 1)] | ForEach-Object { Write-Host "[$([int]$sw.Elapsed.TotalSeconds)s] $_" } }
        $script:pos = $lines.Count
    }
}
while (-not $p.HasExited) {
    Flush-Log
    if ($sw.Elapsed.TotalSeconds -gt $TimeoutSec) {
        Write-Host "::error::$Mode 模式超时（$TimeoutSec 秒），诊断信息："
        Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $p.Id -or $_.Name -match 'pnputil|essetup|powershell|drvinst|eSf' } |
            Format-Table ProcessId, ParentProcessId, Name, CommandLine -AutoSize | Out-String -Width 400 | Write-Host
        Get-Printer | Format-Table Name, DriverName, PortName | Out-String | Write-Host
        Get-PrinterDriver | Format-Table Name | Out-String | Write-Host
        Stop-Process -Id $p.Id -Force
        exit 1
    }
    Start-Sleep 2
}
Flush-Log
Write-Host "$Mode 模式结束，用时 $([int]$sw.Elapsed.TotalSeconds) 秒，返回码 $($p.ExitCode)"
exit $p.ExitCode
