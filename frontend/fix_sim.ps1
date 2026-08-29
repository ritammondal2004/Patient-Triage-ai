
$content = Get-Content -Raw src/pages/SimulationPage.tsx
$content = $content -replace "scenarios\?\.map", "((scenarios as any)?.scenarios || (Array.isArray(scenarios) ? scenarios : []))?.map"
$content = $content -replace "runSimulation\.data\.metrics\.mean_wait_minutes\.toFixed", "(runSimulation.data.metrics.mean_wait_minutes || 0).toFixed"
$content = $content -replace "runSimulation\.data\.metrics\.p90_wait_minutes\.toFixed", "(runSimulation.data.metrics.p90_wait_minutes || 0).toFixed"
$content = $content -replace "runSimulation\.data\.metrics\.doctor_utilisation \* 100", "(runSimulation.data.metrics.doctor_utilisation || 0) * 100"
$content = $content -replace "runSimulation\.data\.metrics\.bed_utilisation \* 100", "(runSimulation.data.metrics.bed_utilisation || 0) * 100"
$content = $content -replace "Object\.entries\(runSimulation\.data\.metrics\.by_priority\)", "Object.entries(runSimulation.data.metrics.by_priority || {})"
$content = $content -replace "Object\.keys\(runSimulation\.data\.metrics\.by_priority\)", "Object.keys(runSimulation.data.metrics.by_priority || {})"
$content = $content -replace "runSimulation\.data\.metrics\.caught_by_reassessment", "runSimulation.data.metrics.escalations"
$content = $content -replace "Escalations triggered: \{runSimulation\.data\.metrics\.escalations\}", "High risk treated: {runSimulation.data.metrics.high_risk_treated}"
$content = $content -replace "m\.mean_wait\.toFixed", "(m.mean_wait || 0).toFixed"
$content = $content -replace "m\.p90_wait\.toFixed", "(m.p90_wait || 0).toFixed"
$content = $content -replace "\(m\.within_target_pct \* 100\)", "(m.within_target_pct || 0)"
Set-Content -Path src/pages/SimulationPage.tsx -Value $content

