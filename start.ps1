param([int]$Port = 4180, [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    if (-not $SkipInstall) {
        & $pythonExe -m pip install --upgrade 'pip>=26.2.1' 'setuptools>=84.0.0'
        if ($LASTEXITCODE -ne 0) { throw 'Could not update the Python package tools.' }
        & $pythonExe -m pip install -r backend\requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Could not install the backend dependencies.' }
        Push-Location frontend
        try {
            npm.cmd ci --no-fund --no-audit
            if ($LASTEXITCODE -ne 0) { throw 'Could not install the frontend dependencies.' }
            npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw 'Could not build the frontend.' }
        } finally { Pop-Location }
    }
    $env:TEAM_NAV_ORIGINS = "http://127.0.0.1:$Port,http://localhost:$Port,http://127.0.0.1:5173,http://localhost:5173"
    Push-Location backend
    try {
        & $pythonExe -m app.cli init
        if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the database.' }
        Write-Host "Open http://127.0.0.1:$Port"
        & $pythonExe -m app.cli serve --port $Port
    } finally { Pop-Location }
} finally { Pop-Location }
