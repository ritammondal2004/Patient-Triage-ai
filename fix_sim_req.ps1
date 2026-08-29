
$content = Get-Content -Raw app/models/schemas.py
$content = $content -replace "hours: float = Field\(8\.0", "hours: float = Field(24.0"
Set-Content -Path app/models/schemas.py -Value $content

