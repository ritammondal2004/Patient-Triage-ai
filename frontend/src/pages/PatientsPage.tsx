import React, { useState } from 'react';
import { usePatients, usePatientVisits, useVisitAssessments } from '@/hooks/use-api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight, Activity } from 'lucide-react';
import { PRIORITY_CONFIG, CONFIDENCE_CONFIG } from '@/lib/utils';
import type { AssessmentOut } from '@/types/api';

export function PatientsPage() {
  const { data: patients, isLoading } = usePatients(100);
  const [selectedPatientCode, setSelectedPatientCode] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900">Patients</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle>Directory</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Age/Gen</TableHead>
                    <TableHead>History</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <TableRow><TableCell colSpan={3} className="text-center py-4">Loading...</TableCell></TableRow>
                  ) : (
                    patients?.map(p => (
                      <TableRow 
                        key={p.id} 
                        className={`cursor-pointer hover:bg-slate-50 ${selectedPatientCode === p.patient_code ? 'bg-blue-50' : ''}`}
                        onClick={() => setSelectedPatientCode(p.patient_code)}
                      >
                        <TableCell className="font-medium">{p.patient_code}</TableCell>
                        <TableCell>{p.age} {p.gender.charAt(0)}</TableCell>
                        <TableCell>
                          {p.has_prior_history ? (
                            <Badge variant="secondary" className="text-xs">Yes ({p.prior_ed_visits})</Badge>
                          ) : (
                            <span className="text-muted-foreground text-sm">No</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          {selectedPatientCode ? (
            <PatientDetail code={selectedPatientCode} />
          ) : (
            <Card className="flex items-center justify-center h-64 text-slate-500">
              Select a patient from the directory to view details.
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function PatientDetail({ code }: { code: string }) {
  const { data: visits, isLoading } = usePatientVisits(code);
  const [expandedVisitId, setExpandedVisitId] = useState<number | null>(null);

  if (isLoading) return <Card className="p-6 text-center">Loading visits...</Card>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Visits for {code}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {visits?.length === 0 ? (
          <p className="text-slate-500">No visits found.</p>
        ) : (
          visits?.map(visit => (
            <div key={visit.id} className="border rounded-lg p-4">
              <div 
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setExpandedVisitId(expandedVisitId === visit.id ? null : visit.id)}
              >
                <div>
                  <h4 className="font-semibold">{visit.chief_complaint}</h4>
                  <p className="text-sm text-slate-500">
                    {new Date(visit.arrived_at).toLocaleString()} • {visit.arrival_mode} • Status: {visit.status}
                  </p>
                </div>
                <Button variant="ghost" size="sm">
                  {expandedVisitId === visit.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </Button>
              </div>

              {expandedVisitId === visit.id && (
                <div className="mt-4 pt-4 border-t">
                  <VisitAssessments visitId={visit.id} />
                </div>
              )}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function VisitAssessments({ visitId }: { visitId: number }) {
  const { data: assessments, isLoading } = useVisitAssessments(visitId);

  if (isLoading) return <p className="text-sm text-slate-500">Loading assessments...</p>;
  
  return (
    <div className="space-y-3">
      <h5 className="font-medium text-sm flex items-center"><Activity className="mr-2 h-4 w-4 text-blue-500"/> Assessment History</h5>
      {assessments?.length === 0 ? (
        <p className="text-sm text-slate-500">No assessments found.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
               <TableHead>Time</TableHead>
               <TableHead>Trigger</TableHead>
               <TableHead>Priority</TableHead>
               <TableHead>Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {assessments?.map((a: AssessmentOut) => (
              <TableRow key={a.id}>
                <TableCell className="text-sm whitespace-nowrap text-slate-600">
                  {new Date(a.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                </TableCell>
                <TableCell className="text-sm capitalize">{a.trigger.replace(/_/g, ' ')}</TableCell>
                <TableCell>
                  <Badge style={{ backgroundColor: PRIORITY_CONFIG[a.final_priority]?.bg, color: PRIORITY_CONFIG[a.final_priority]?.color }}>
                    {a.priority_label}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" style={{ backgroundColor: CONFIDENCE_CONFIG[a.confidence_label]?.bg, color: CONFIDENCE_CONFIG[a.confidence_label]?.color, borderColor: CONFIDENCE_CONFIG[a.confidence_label]?.color }}>
                    {a.confidence_label}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
