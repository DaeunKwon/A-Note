Write-Host "======================================"
Write-Host "  A-Note start (PowerShell)"
Write-Host "======================================"
Write-Host ""

# 8000 포트를 이미 점유한 프로세스가 있으면 새 서버가 뜨지 않고 기존(오래된) 인스턴스로 붙을 수 있음
$portPids = @()
try {
  $portPids = netstat -ano | Select-String ":8000" | ForEach-Object {
    $parts = (($_.Line -replace "\s+", " ").Trim().Split(" "))
    if ($parts.Length -ge 5 -and $parts[3] -eq "LISTENING") { [int]$parts[4] }
  } | Sort-Object -Unique
} catch {}

if ($portPids.Count -gt 0) {
  Write-Host "Cleaning up existing listeners on :8000 ..."
  foreach ($portPid in $portPids) {
    try { Stop-Process -Id $portPid -Force -ErrorAction Stop } catch {}
  }
  Start-Sleep -Milliseconds 500
}

# 추가 안전장치: server.py 잔여 python 정리
$stale = Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq "python.exe" -and $_.CommandLine -match "server.py"
}
if ($stale) {
  Write-Host "Cleaning up stale server.py processes..."
  $stale | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
  }
  Start-Sleep -Milliseconds 300
}

Write-Host "Installing packages..."
python -m pip install -r .\Requirements.txt -q
Write-Host ""
Write-Host "Server: http://localhost:8000"
Write-Host "Open this URL in browser."
Write-Host ""
python -m uvicorn server:app --host 0.0.0.0 --port 8000
