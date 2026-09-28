# Registra el agente de impresión Atlas en el Programador de tareas de ESTA cuenta
# y no declara éxito sin que /health responda. Lo llama el instalador (Inno Setup).
#   registrar.ps1 -Exe "C:\...\atlas-print-agent.exe"
#   registrar.ps1 -Quitar
# Tarea y no servicio: un servicio corre en la sesión 0 y no ve las impresoras
# instaladas por usuario (spec §6.3).
param([string]$Exe, [string]$Version, [switch]$Quitar)
$ErrorActionPreference = "Stop"
$Tarea = "Atlas Print Agent"
$Estado = Join-Path $env:LOCALAPPDATA "AtlasPrintAgent"
New-Item -ItemType Directory -Force -Path $Estado | Out-Null
$Bitacora = Join-Path $Estado "instalador.log"
function Anotar([string]$m) { $l = "$(Get-Date -Format s)  $m"; Write-Output $l; Add-Content -Path $Bitacora -Value $l -Encoding UTF8 }

function Detener-Agente {
    Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue | Stop-ScheduledTask -ErrorAction SilentlyContinue
    Get-Process -Name "atlas-print-agent" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

if ($Quitar) {
    Detener-Agente
    Unregister-ScheduledTask -TaskName $Tarea -Confirm:$false -ErrorAction SilentlyContinue
    Anotar "Tarea '$Tarea' eliminada."
    exit 0
}

# 1. Modo manual: primero la ventana de impresora_win.bat (su :loop relanza el
#    agente cada 5 s), luego el python del agente.
Detener-Agente
$procesos = Get-CimInstance Win32_Process
# Carpetas del modo manual, leídas de los procesos antes de matarlos y buscadas en
# el perfil: de ahí sale el certificado y ahí se retira el lanzador viejo.
$legado = New-Object System.Collections.Generic.List[string]
foreach ($p in $procesos) {
    if ($p.CommandLine -match '([A-Za-z]:\\[^"]*?)\\impresora_win\.bat') { $legado.Add($Matches[1]) }
    if ($p.CommandLine -match '([A-Za-z]:\\[^"]*?)\\core\\main\.py') { $legado.Add($Matches[1]) }
}
Get-ChildItem -Path $env:USERPROFILE -Filter "impresora_win.bat" -Recurse -Depth 8 -File -ErrorAction SilentlyContinue |
    ForEach-Object { $legado.Add($_.DirectoryName) }
$legado = @($legado | Sort-Object -Unique)
foreach ($d in $legado) { Anotar "Modo manual encontrado en $d" }
$procesos | Where-Object { $_.Name -eq "cmd.exe" -and $_.CommandLine -match "impresora_win\.bat" } |
    ForEach-Object { Anotar "Deteniendo la ventana del modo manual (PID $($_.ProcessId))"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$procesos | Where-Object { $_.Name -match "^pythonw?\.exe$" -and $_.CommandLine -match "core\\main\.py" } |
    ForEach-Object { Anotar "Deteniendo el agente manual (PID $($_.ProcessId))"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 2. Certificado: se conserva el que el navegador ya aceptó.
$Certs = Join-Path $Estado "certs"
if ((Test-Path (Join-Path $Certs "cert.pem")) -and (Test-Path (Join-Path $Certs "key.pem"))) {
    Anotar "Certificado existente conservado."
} else {
    # Primero el de la carpeta que la caja usaba de verdad; si no, el más reciente del perfil.
    $previo = $legado | ForEach-Object { Get-Item (Join-Path $_ "core\certs\cert.pem") -ErrorAction SilentlyContinue } |
        Where-Object { Test-Path (Join-Path $_.DirectoryName "key.pem") } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $previo) { $previo = Get-ChildItem -Path $env:USERPROFILE -Filter "cert.pem" -Recurse -Depth 8 -File -ErrorAction SilentlyContinue |
        Where-Object { $_.DirectoryName -match "\\core\\certs$" -and (Test-Path (Join-Path $_.DirectoryName "key.pem")) } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 }
    if ($previo) {
        New-Item -ItemType Directory -Force -Path $Certs | Out-Null
        Copy-Item (Join-Path $previo.DirectoryName "cert.pem"), (Join-Path $previo.DirectoryName "key.pem") -Destination $Certs
        Anotar "Certificado conservado desde $($previo.DirectoryName)."
    } else {
        Anotar "No había certificado previo: el agente generará uno nuevo (habrá que aceptarlo una vez en el navegador)."
    }
}

# 2b. El lanzador viejo pasa a abrir el agente nuevo. El original "libera" el
#     puerto 9100 matando lo que lo tenga: con un doble clic de costumbre tumbaría
#     al agente instalado. Reescrito, solo muestra "ya está activo".
foreach ($d in $legado) {
    $bat = Join-Path $d "impresora_win.bat"
    if (-not (Test-Path $bat)) { continue }
    if ((Get-Content -Raw $bat) -match "atlas-print-agent instalado") { continue }
    Copy-Item $bat "$bat.retirado" -Force
    @(
        "@echo off",
        "rem Esta PC ya usa el atlas-print-agent instalado: arranca solo al iniciar sesion.",
        "rem Este archivo solo lo abre (dira que ya esta activo). El original quedo como .retirado.",
        "start `"`" `"$Exe`""
    ) | Set-Content -Path $bat -Encoding ASCII
    Anotar "Lanzador viejo convertido en atajo al agente nuevo: $bat"
}

# 3. agent.conf de ejemplo, solo si no existe.
$Conf = Join-Path $Estado "agent.conf"
if (-not (Test-Path $Conf)) {
    @(
        "# Configuración del agente de impresión Atlas. Una línea CLAVE=valor.",
        "# Después de editarlo: cierra sesión y vuelve a entrar.",
        "#",
        "# Dominios extra del punto de venta, separados por coma. localhost,",
        "# *.up.railway.app y (*.)atlasone.com.mx ya se aceptan sin escribir nada.",
        "# ATLAS_AGENT_ORIGINS=https://pos.micliente.com"
    ) | Set-Content -Path $Conf -Encoding UTF8
}
$Puerto = 9100
$linea = Select-String -Path $Conf -Pattern "^\s*ATLAS_AGENT_PORT\s*=\s*(\d+)" | Select-Object -Last 1
if ($linea) { $Puerto = [int]$linea.Matches[0].Groups[1].Value }

# 4. Tarea programada.
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$xml = Get-Content -Raw -Path (Join-Path $PSScriptRoot "tarea.xml")
$xml = $xml.Replace("__USUARIO__", [System.Security.SecurityElement]::Escape($usuario))
$xml = $xml.Replace("__EXE__", [System.Security.SecurityElement]::Escape($Exe))
Register-ScheduledTask -TaskName $Tarea -Xml $xml -Force | Out-Null
Start-ScheduledTask -TaskName $Tarea
Anotar "Tarea '$Tarea' registrada para $usuario y arrancada."

# 5. Verificación real.
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $r = & curl.exe -sk --noproxy "*" --max-time 2 "https://127.0.0.1:$Puerto/health" 2>$null
    if ($r -match ('"version":"' + [regex]::Escape($Version) + '"')) { Anotar "Agente respondiendo: $r"; exit 0 }
}
$dueno = Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($dueno) { Anotar "El puerto $Puerto lo tiene otro programa: $((Get-Process -Id $dueno.OwningProcess).ProcessName)" }
Anotar "El agente $Version NO respondió en https://127.0.0.1:$Puerto/health"
exit 1
