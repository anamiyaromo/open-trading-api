$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$MainPath = Join-Path $ProjectDir "main.py"
$PythonPath = "C:\Python314\python.exe"
$LauncherLog = Join-Path $ProjectDir "auto_trader_launcher.log"

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        ($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and
        $_.CommandLine -like "*samsung_auto_trader*main.py*"
    }

if ($existing) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Auto trader is already running. PID(s): $($existing.ProcessId -join ', ')" |
        Add-Content -Path $LauncherLog -Encoding UTF8
    exit 0
}

"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Starting auto trader from $MainPath" |
    Add-Content -Path $LauncherLog -Encoding UTF8

Set-Location $ProjectDir
& $PythonPath $MainPath

"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Auto trader stopped with exit code $LASTEXITCODE" |
    Add-Content -Path $LauncherLog -Encoding UTF8
