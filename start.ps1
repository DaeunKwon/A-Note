Write-Host "======================================"
Write-Host "  A-Note start (PowerShell)"
Write-Host "======================================"
Write-Host ""
Write-Host "Installing packages..."
python -m pip install -r .\Requirements.txt -q
Write-Host ""
Write-Host "Server: http://localhost:8000"
Write-Host "Open this URL in browser."
Write-Host ""
python .\server.py
