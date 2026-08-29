
$files = @("app/api/routes_queue.py", "app/api/routes_patients.py", "app/api/routes_overrides.py", "app/api/routes_triage.py")
foreach ($f in $files) {
    $content = Get-Content -Raw $f
    $content = $content -replace "db: DbSession, _: ApiKey = None, hospital: DemoHospital", "db: DbSession, hospital: DemoHospital, _: ApiKey = None"
    Set-Content -Path $f -Value $content
}

