# Offline installer: creates .venv from bundled wheels, no internet needed.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Have-Py { try { py -3.11 -c "import sys" 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false } }
if (-not (Have-Py)) {
    if (-not (Test-Path python-installer.exe)) { throw "Python 3.11 not found. Install it first: winget install Python.Python.3.11" }
    $sig = Get-AuthenticodeSignature python-installer.exe
    if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "Python Software Foundation") { throw "python-installer.exe signature check failed" }
    Write-Host "Installing Python (per-user, silent)..."
    Start-Process .\python-installer.exe -ArgumentList "/quiet","InstallAllUsers=0","PrependPath=1","Include_launcher=1","Include_test=0" -Wait
    $env:Path = [Environment]::GetEnvironmentVariable("Path","User") + ";" + [Environment]::GetEnvironmentVariable("Path","Machine")
}
py -3.11 -m venv .venv
if (Test-Path wheels) { .\.venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements.txt }
else { .\.venv\Scripts\python.exe -m pip install -r requirements.txt; .\.venv\Scripts\python.exe -m pip install pywin32 colorama }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path config.yaml)) { Copy-Item config.example.yaml config.yaml }
if (Test-Path platform-tools\adb.exe) {
    (Get-Content .env) -replace '^ADB_BINARY=.*', ("ADB_BINARY=" + (Resolve-Path platform-tools\adb.exe)) | Set-Content .env
}
$tok = .\.venv\Scripts\python.exe -c "import secrets;print(secrets.token_urlsafe(48))"
(Get-Content .env) -replace '^AUTOMATION_API_TOKEN=.*', "AUTOMATION_API_TOKEN=$tok" | Set-Content .env
Write-Host "Installed. Edit .env (BIND_HOST = your ZeroTier IP) and config.yaml (adb_endpoint), then run:"
Write-Host "  .\.venv\Scripts\python.exe -m src.main"
Write-Host "Your API token is in .env (AUTOMATION_API_TOKEN)."
