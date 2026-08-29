
$content = Get-Content -Raw src/pages/OverridesPage.tsx
$content = $content -replace "useOverrides, useCreateOverride", "useOverrides, useCreateOverride, useQueue"
$content = $content -replace "const \[assessmentId, setAssessmentId\]", "const { data: queue } = useQueue();`n  const [assessmentId, setAssessmentId]"

$replacement = @"
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="assessmentId">Assessment ID *</Label>
                  <div className="flex gap-2">
                    <Input id="assessmentId" type="number" value={assessmentId} onChange={(e) => setAssessmentId(e.target.value)} required placeholder="ID" className="w-24" />
                    <select
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                      onChange={(e) => setAssessmentId(e.target.value)}
                      value=""
                    >
                      <option value="" disabled>Or select from Active Queue...</option>
                      {queue?.map((q: any) => (
                        <option key={q.assessment_id} value={q.assessment_id}>
                          {q.patient_code} (P{q.priority}) - {q.chief_complaint}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
"@
$content = $content -replace "(?s)<div className=`"grid grid-cols-2 gap-4`">\s*<div className=`"space-y-2`">\s*<Label htmlFor=`"assessmentId`">Assessment ID \*</Label>\s*<Input id=`"assessmentId`" type=`"number`" value=\{assessmentId\} onChange=\{\(e\) => setAssessmentId\(e.target.value\)\} required />\s*</div>", $replacement
Set-Content -Path src/pages/OverridesPage.tsx -Value $content

