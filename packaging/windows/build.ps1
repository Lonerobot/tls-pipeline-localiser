param(
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$spec = Join-Path $PSScriptRoot "theline-pipeline.spec"
$iss = Join-Path $PSScriptRoot "TheLinePipeline.iss"
$pythonRequirements = Join-Path $PSScriptRoot "requirements-build.txt"
$stagingName = "p$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$stagingRoot = Join-Path $repoRoot "build\$stagingName"
$appDist = Join-Path $stagingRoot "dist\TheLinePipeline"

if (-not $PythonExecutable) {
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExecutable = $venvPython
    } else {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            $PythonExecutable = $launcher.Source
        } else {
            $python = Get-Command python.exe -ErrorAction SilentlyContinue
            if (-not $python) {
                throw "Python 3.11 or newer is required. Install Python or pass -PythonExecutable."
            }
            $PythonExecutable = $python.Source
        }
    }
}

Push-Location $repoRoot
try {
    & $PythonExecutable -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.11 or newer is required."
    }

    & $PythonExecutable -m pip install -e ".[tray]" -r $pythonRequirements
    if ($LASTEXITCODE -ne 0) {
        throw "Installing the application and Windows build dependencies failed."
    }

    & $PythonExecutable -m PyInstaller --noconfirm --clean --distpath (Join-Path $stagingRoot "dist") --workpath build\pyinstaller $spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

    $app = Join-Path $appDist "TheLinePipeline.exe"
    $smoke = Start-Process -FilePath $app -ArgumentList "--smoke-test" -Wait -PassThru
    if ($smoke.ExitCode -ne 0) {
        throw "The packaged application smoke test failed."
    }

    & $PythonExecutable -I -S (Join-Path $PSScriptRoot "check_pipeline.py") (Join-Path $appDist "_internal")
    if ($LASTEXITCODE -ne 0) {
        throw "The packaged DCC pipeline initialization test failed."
    }

    $version = & $PythonExecutable -c "import pathlib,tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
    if ($LASTEXITCODE -ne 0 -or -not $version) {
        throw "Could not read the project version from pyproject.toml."
    }

    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $iscc) {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
        )
        $isccPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    } else {
        $isccPath = $iscc.Source
    }
    if (-not $isccPath) {
        throw "The app bundle passed its smoke test, but Inno Setup 6 was not found. Install Inno Setup and rerun this script."
    }

    & $isccPath $iss "/DAppVersion=$version" "/DAppBuildDir=$appDist"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed."
    }

    Write-Output "Installer created: dist\installer\TheLinePipeline-Setup-$version-x64.exe"
} finally {
    if (Test-Path $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
    Pop-Location
}
