
$content = Get-Content -Raw src/pages/OverridesPage.tsx
$content = $content -replace "\} else \{\s*setErrorMsg\(err\.message \|\| 'Failed to submit override\. Check if the assessment ID is valid\.'[^}]+\}\s*\}\s*\}\s*\)\;", "} else {`n              setErrorMsg(err.message || 'Failed to submit override. Check if the assessment ID is valid.');`n            }`n          }`n        }`n      );`n"
Set-Content -Path src/pages/OverridesPage.tsx -Value $content

