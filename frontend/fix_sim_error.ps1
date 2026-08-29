
$content = Get-Content -Raw src/pages/SimulationPage.tsx
$replacement = @"
      {runSimulation.isError && (
        <div className="p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
          Simulation failed to run. Please check your network or try a different scenario.
        </div>
      )}
      {runSimulation.data && (
"@
$content = $content -replace "\{runSimulation\.data && \(", $replacement
Set-Content -Path src/pages/SimulationPage.tsx -Value $content

