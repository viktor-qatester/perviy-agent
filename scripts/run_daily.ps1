# Ежедневный запуск Первого Агента в 05:00 (Минск)
# Настройка: Планировщик заданий Windows -> Создать задачу -> Триггер 05:00

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "scheduler.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Set-Location $ProjectRoot
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "[$stamp] start"

& $Python "src/main.py" --send 2>&1 | Add-Content -Path $LogFile

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "[$stamp] exit $LASTEXITCODE"

exit $LASTEXITCODE
