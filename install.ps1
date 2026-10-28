param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment. Install Python 3.10+ or pass -Python with its full path.' }
}
& $venvPython -m pip install -e (Join-Path $PSScriptRoot 'agent-harness[dev]')
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
Write-Host 'Installed. Run .\toutiao.cmd --help or .\toutiao.cmd hot'
