$processes = Get-CimInstance Win32_Process |
    Where-Object {
        ($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and
        $_.CommandLine -like "*samsung_auto_trader*main.py*"
    }

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force
}

Write-Host "Stopped $($processes.Count) auto trader process(es)."
