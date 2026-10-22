$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') { throw 'Construir el instalador requiere Windows nativo' }
python -m pip install -e './backend' -r packaging/requirements-build.txt
if ($LASTEXITCODE) { throw 'Falló instalación de herramientas de build' }
npm --prefix frontend ci
if ($LASTEXITCODE) { throw 'Falló npm ci' }
npm --prefix frontend run build
if ($LASTEXITCODE) { throw 'Falló build frontend' }
python packaging/build.py
if ($LASTEXITCODE) { throw 'Falló PyInstaller' }
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) { $iscc = Get-Item "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue }
if (-not $iscc) { throw 'Instalá Inno Setup 6.x; la PC cliente no lo requiere' }
$isccPath = if ($iscc.Source) { $iscc.Source } else { $iscc.FullName }
Write-Output ('Inno Setup: ' + (Get-Item $isccPath).VersionInfo.ProductVersion)
$productVersion = python -c "import tomllib; print(tomllib.load(open('backend/pyproject.toml','rb'))['project']['version'])"
& $isccPath "/DAppVersion=$productVersion" packaging/windows.iss
if ($LASTEXITCODE) { throw 'Falló Inno Setup' }
Get-ChildItem dist/installer/*.exe | Get-FileHash -Algorithm SHA256 | Format-List
