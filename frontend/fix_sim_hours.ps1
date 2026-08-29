
$content = Get-Content -Raw src/pages/SimulationPage.tsx
$content = $content -replace "const \[hours, setHours\] = useState\(8\);", "const [hours, setHours] = useState(24);"
Set-Content -Path src/pages/SimulationPage.tsx -Value $content

