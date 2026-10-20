# Programa checkin.py en el Programador de tareas de Windows (IP residencial, sin GitHub).
# Uso (una sola vez, en PowerShell):
#   1. Pega tus cookies en contingencia\cookie.txt (una sola línea, NO se sube a git).
#   2. pip install seleniumbase
#   3. powershell -ExecutionPolicy Bypass -File contingencia\programar_tarea_windows.ps1
# La tarea corre a las 19:15 (hora Perú, justo después del reinicio de las 9:00 KST)
# y, si el PC estaba apagado o dormido a esa hora, se ejecuta en cuanto vuelva a estar disponible.

$raiz = Split-Path -Parent $PSScriptRoot
$cookieFile = Join-Path $PSScriptRoot "cookie.txt"
$python = (Get-Command python).Source

if (-not (Test-Path $cookieFile)) {
    Write-Error "Falta $cookieFile con el valor de CAVEDUCK_COOKIE."
    exit 1
}

$cmd = "`$env:CAVEDUCK_COOKIE = (Get-Content -Raw '$cookieFile').Trim(); Set-Location '$raiz'; & '$python' checkin.py *> '$raiz\contingencia\ultimo_log.txt'"

$accion = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
$disparador = New-ScheduledTaskTrigger -Daily -At "19:15"
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName "Caveduck Check-in" -Action $accion -Trigger $disparador -Settings $ajustes -Force | Out-Null
Write-Host "Tarea 'Caveduck Check-in' registrada. Log en contingencia\ultimo_log.txt"
