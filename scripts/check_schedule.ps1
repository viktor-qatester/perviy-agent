# Диагностика: откуда мог прийти лишний отчёт (GitHub vs локальный ПК).
# Запуск: powershell -ExecutionPolicy Bypass -File scripts/check_schedule.ps1

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LogFile = Join-Path $ProjectRoot "logs\scheduler.log"
$EnvFile = Join-Path $ProjectRoot ".env"

Write-Host "=== Первый Агент: диагностика расписания ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "1) GitHub Actions (облако)" -ForegroundColor Yellow
Write-Host "   Расписание: понедельник и пятница, 05:00 Минск"
Write-Host "   Проверка: github.com -> Actions -> IT digest -> фильтр по дате"
Write-Host "   Если в Actions нет run на дату, а сообщение пришло — источник локальный."
Write-Host ""

Write-Host "2) Планировщик заданий Windows" -ForegroundColor Yellow
$patterns = @("perviy", "первый", "run_daily", "main.py", "агент")
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
    $info = ($_.TaskName + " " + $_.TaskPath + " " + ($_.Actions | ForEach-Object { $_.Execute + " " + $_.Arguments }) -join " ")
    foreach ($p in $patterns) {
        if ($info -match $p) { return $true }
    }
    return $false
}

if ($tasks) {
    foreach ($task in $tasks) {
        $state = (Get-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath).State
        $action = ($task.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join "; "
        Write-Host "   [НАЙДЕНО] $($task.TaskPath)$($task.TaskName) | State=$state"
        Write-Host "            $action"
    }
    Write-Host ""
    Write-Host "   Если задача «ежедневно» и вызывает run_daily.ps1 — раньше слала каждый день."
    Write-Host "   После обновления run_daily.ps1 лишние дни пропускаются; можно также отключить задачу."
} else {
    Write-Host "   Задач с похожими именами не найдено."
}
Write-Host ""

Write-Host "3) Локальный лог run_daily.ps1" -ForegroundColor Yellow
if (Test-Path $LogFile) {
    Write-Host "   Файл: $LogFile"
    Write-Host "   Последние строки:"
    Get-Content $LogFile -Tail 15 | ForEach-Object { Write-Host "   $_" }
} else {
    Write-Host "   $LogFile не найден (run_daily.ps1, возможно, не запускался)."
}
Write-Host ""

Write-Host "4) .env — локальный бот" -ForegroundColor Yellow
if (Test-Path $EnvFile) {
    $lines = Get-Content $EnvFile | Where-Object {
        $_ -match '^(NOTIFY_VIA|SCHEDULE_ENABLED|SCHEDULE_DAYS|SCHEDULE_TIME|SCHEDULE_SLOTS|TIMEZONE)='
    }
    foreach ($line in $lines) {
        Write-Host "   $line"
    }
    Write-Host ""
    Write-Host "   Если SCHEDULE_ENABLED=true и бот запущен (python src/main.py --bot),"
    Write-Host "   отчёт может идти по SCHEDULE_DAYS/SCHEDULE_SLOTS даже без Windows Task Scheduler."
} else {
    Write-Host "   .env не найден в $ProjectRoot"
}
Write-Host ""
Write-Host "=== Конец диагностики ===" -ForegroundColor Cyan
