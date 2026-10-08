# Запуск отчёта Первого Агента — только понедельник и пятница, ~05:00 (Минск).
# Основной cron: GitHub Actions (.github/workflows/daily-digest.yml).
# Этот скрипт — запасной/локальный; в Планировщике Windows ставьте триггер «ежедневно»,
# но сам скрипт пропустит лишние дни (вт–чт, сб–вс).

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "scheduler.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log($Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$stamp] $Message"
}

Set-Location $ProjectRoot

$today = Get-Date
$allowed = @([DayOfWeek]::Monday, [DayOfWeek]::Friday)
if ($today.DayOfWeek -notin $allowed) {
    Write-Log "skip: today is $($today.DayOfWeek), report only Mon/Fri"
    exit 0
}

Write-Log "start ($($today.DayOfWeek))"

if (-not (Test-Path $Python)) {
    Write-Log "error: python not found at $Python"
    exit 1
}

& $Python "src/main.py" --send 2>&1 | ForEach-Object { Write-Log $_ }

Write-Log "exit $LASTEXITCODE"
exit $LASTEXITCODE
