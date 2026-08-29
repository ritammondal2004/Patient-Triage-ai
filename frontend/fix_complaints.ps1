
$content = Get-Content -Raw src/pages/IntakePage.tsx
$replacement = @"
const COMPLAINTS = [
  'chest_pain', 'abdominal_pain', 'shortness_of_breath', 'headache', 'trauma',
  'fever', 'seizure', 'cardiac_arrest', 'allergic_reaction', 'altered_consciousness',
  'back_pain', 'dizziness', 'nausea', 'laceration', 'fracture', 'stroke', 'bleeding', 'other'
].sort();
"@
$content = $content -replace "(?s)const COMPLAINTS = \[.*?\];", $replacement
Set-Content -Path src/pages/IntakePage.tsx -Value $content

