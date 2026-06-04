$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunnerPath = Join-Path $ProjectDir "run_auto_trader.ps1"

Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $RunnerPath) `
    -WindowStyle Hidden
