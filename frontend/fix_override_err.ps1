
$content = Get-Content -Raw src/pages/OverridesPage.tsx
$replacement = @"
          onError: (err: any) => {
            if (err.status === 409 || err.message?.includes("409")) {
              setErrorMsg('This assessment has already been overridden.');
            } else if (err.status === 404 || err.message?.includes("404")) {
              setErrorMsg('Assessment not found. Please provide a valid ID.');
            } else {
              setErrorMsg(err.message || 'Failed to submit override. Check if the assessment ID is valid.');
            }
          }
"@
$content = $content -replace "(?s)onError: \(err: any\) => \{.*?\n\s*\}\n\s*\}", ($replacement + "`n        }")
Set-Content -Path src/pages/OverridesPage.tsx -Value $content

