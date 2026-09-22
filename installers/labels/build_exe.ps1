# Genera dist\Atlas Labels.exe (sin consola, un solo archivo) y un acceso directo en el escritorio.
# Uso, desde PowerShell en Windows:  .\installers\labels\build_exe.ps1
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

Write-Host "Instalando dependencias en el Python de Windows..."
python -m pip install --quiet --upgrade pyinstaller
python -m pip install --quiet -r requirements-labels.txt

Write-Host "Empaquetando..."
python -m PyInstaller --noconsole --onefile --clean --name "Atlas Labels" --collect-submodules atlas_labels launch_gui.py

$exe = Join-Path $root "dist\Atlas Labels.exe"
if (-not (Test-Path $exe)) { throw "No se generó $exe" }

$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "Atlas Labels.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = Split-Path $exe
$shortcut.Description = "Impresión de etiquetas Zebra desde el catálogo"
$shortcut.Save()

Write-Host "Ejecutable:     $exe"
Write-Host "Acceso directo: $lnk"
