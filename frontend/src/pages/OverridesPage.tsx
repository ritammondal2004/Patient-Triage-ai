import React, { useState, useEffect } from 'react';
import { useOverrides, useCreateOverride, useQueue } from '@/hooks/use-api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { PRIORITY_CONFIG } from '@/lib/utils';
import { ArrowUp, ArrowDown } from 'lucide-react';

export function OverridesPage() {
  const { data: overrides, isLoading, refetch } = useOverrides(50);
  const createOverride = useCreateOverride();

  const { data: queue } = useQueue();
  const [assessmentId, setAssessmentId] = useState('');
  const [clinicianId, setClinicianId] = useState('');
  const [clinicianRole, setClinicianRole] = useState('triage_nurse');
  const [overridePriority, setOverridePriority] = useState<number | ''>('');
  const [reasonCode, setReasonCode] = useState('clinical_judgement');
  const [reasonText, setReasonText] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    // Populate from query param if available (e.g. from Queue override button, ideally needs assessment ID but we can start here)
    const params = new URLSearchParams(window.location.search);
    const visitId = params.get('visit');
    // Note: Usually we need the assessment_id not visit_id, but the user would enter it manually or via a different flow
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (!assessmentId || !clinicianId || overridePriority === '' || reasonText.length < 10 || !acknowledged) {
      setErrorMsg('Please fill all required fields correctly.');
      return;
    }

    createOverride.mutate(
      {
        assessmentId: parseInt(assessmentId, 10),
        data: {
          clinician_id: clinicianId,
          clinician_role: clinicianRole,
          override_priority: overridePriority,
          reason_code: reasonCode,
          reason_text: reasonText,
          acknowledged_ai_recommendation: acknowledged,
        },
      },
      {
        onSuccess: () => {
          setAssessmentId('');
          setClinicianId('');
          setReasonText('');
          setOverridePriority('');
          setAcknowledged(false);
          refetch();
        },
        onError: (err: any) => {
          if (err.status === 409 || err.message?.includes("409")) {
            setErrorMsg('This assessment has already been overridden.');
          } else if (err.status === 404 || err.message?.includes("404")) {
            setErrorMsg('Assessment not found. Please provide a valid ID.');
          } else {
            setErrorMsg(
              err.message || 'Failed to submit override. Check if the assessment ID is valid.'
            );
          }
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900">Clinician Overrides</h1>

      <Card>
        <CardHeader>
          <CardTitle>Create Override</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4 max-w-3xl">
            {errorMsg && <div className="p-3 bg-red-50 text-red-600 border border-red-200 rounded-md text-sm">{errorMsg}</div>}

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

              <div className="space-y-2">
                <Label htmlFor="clinicianId">Clinician ID *</Label>
                <Input id="clinicianId" placeholder="e.g. DR-SHARMA" value={clinicianId} onChange={(e) => setClinicianId(e.target.value)} required />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Clinician Role</Label>
                <select
                  className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={clinicianRole}
                  onChange={(e) => setClinicianRole(e.target.value)}
                >
                  <option value="triage_nurse">Triage Nurse</option>
                  <option value="attending">Attending</option>
                  <option value="resident">Resident</option>
                  <option value="specialist">Specialist</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label>Reason Code</Label>
                <select
                  className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={reasonCode}
                  onChange={(e) => setReasonCode(e.target.value)}
                >
                  <option value="clinical_judgement">Clinical Judgement</option>
                  <option value="missed_finding">Missed Finding</option>
                  <option value="patient_deterioration">Patient Deterioration</option>
                  <option value="family_concern">Family Concern</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Override Priority (1-Resuscitation to 5-Non-urgent) *</Label>
              <div className="flex gap-4">
                {[1, 2, 3, 4, 5].map((lvl) => (
                  <label key={lvl} className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="radio"
                      name="priority"
                      value={lvl}
                      checked={overridePriority === lvl}
                      onChange={() => setOverridePriority(lvl)}
                    />
                    <Badge style={{ backgroundColor: PRIORITY_CONFIG[lvl]?.color, color: '#fff' }}>
                      Level {lvl}
                    </Badge>
                  </label>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Reason Text * (min 10 chars)</Label>
              <Textarea
                value={reasonText}
                onChange={(e) => setReasonText(e.target.value)}
                required
                minLength={10}
              />
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="ack"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
                className="h-4 w-4 accent-blue-600 rounded"
              />
              <Label htmlFor="ack" className="font-normal cursor-pointer">
                I acknowledge the AI recommendation and choose to override
              </Label>
            </div>

            <Button type="submit" className="bg-blue-600 hover:bg-blue-700" disabled={createOverride.isPending}>
              {createOverride.isPending ? 'Submitting...' : 'Submit Override'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Override History</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Assmt ID</TableHead>
                <TableHead>Clinician</TableHead>
                <TableHead>AI → Override</TableHead>
                <TableHead>Direction</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-4">
                    Loading...
                  </TableCell>
                </TableRow>
              ) : overrides?.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-4">
                    No overrides recorded.
                  </TableCell>
                </TableRow>
              ) : overrides?.map(o => (
                <TableRow key={o.id}>
                  <TableCell className="font-medium">{o.assessment_id}</TableCell>

                  <TableCell>
                    <div>{o.clinician_id}</div>
                    <div className="text-xs text-slate-500 capitalize">
                      {o.clinician_role.replace(/_/g, ' ')}
                    </div>
                  </TableCell>

                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        style={{
                          borderColor: PRIORITY_CONFIG[o.ai_priority]?.color,
                          color: PRIORITY_CONFIG[o.ai_priority]?.color
                        }}
                      >
                        L{o.ai_priority}
                      </Badge>

                      <span className="text-slate-400">→</span>

                      <Badge
                        style={{
                          backgroundColor: PRIORITY_CONFIG[o.override_priority]?.color,
                          color: '#fff'
                        }}
                      >
                        L{o.override_priority}
                      </Badge>
                    </div>
                  </TableCell>

                  <TableCell>
                    {o.direction === 'escalated' ? (
                      <span className="flex items-center text-red-600 font-medium text-sm">
                        <ArrowUp className="w-4 h-4 mr-1" /> Escalated
                      </span>
                    ) : o.direction === 'de-escalated' ? (
                      <span className="flex items-center text-teal-600 font-medium text-sm">
                        <ArrowDown className="w-4 h-4 mr-1" /> De-escalated
                      </span>
                    ) : (
                      <span className="text-slate-500 text-sm">Same</span>
                    )}
                  </TableCell>

                  <TableCell>
                    <div className="capitalize font-medium text-sm">
                      {o.reason_code.replace(/_/g, ' ')}
                    </div>
                    <div
                      className="text-xs text-slate-500 truncate max-w-[200px]"
                      title={o.reason_text}
                    >
                      {o.reason_text}
                    </div>
                  </TableCell>

                  <TableCell className="text-sm">
                    {new Date(o.created_at).toLocaleDateString()}{' '}
                    {new Date(o.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}