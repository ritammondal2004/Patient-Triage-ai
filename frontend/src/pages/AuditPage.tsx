import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Shield, Scale, AlertTriangle, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

// Assume these are provided by the project's data layer
import { useAuditEvents, useAuditVerify, useAuditPolicy } from '@/hooks/use-api';

export function AuditPage() {
  const { data: verification } = useAuditVerify();
  const { data: policy } = useAuditPolicy();
  
  const [eventType, setEventType] = useState('all');
  const [entityType, setEntityType] = useState('');
  const [limit, setLimit] = useState(50);
  
  const { data: events, isLoading } = useAuditEvents({ event_type: eventType === 'all' ? undefined : eventType, entity_type: entityType, limit });

  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});

  const toggleRow = (id: string) => {
    setExpandedRows(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Audit Trail</h1>
          <p className="text-muted-foreground">DPDP-compliant immutable event log and verification.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Chain Integrity Card */}
        <Card className={cn(
          "border-2",
          verification?.intact === true ? "border-green-500 bg-green-50/50" : 
          verification?.intact === false ? "border-red-500 bg-red-50/50" : ""
        )}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className={cn("h-6 w-6", verification?.intact ? "text-green-600" : "text-red-600")} />
              Chain Integrity
            </CardTitle>
          </CardHeader>
          <CardContent>
            {verification ? (
              verification.intact ? (
                <div className="flex items-center gap-3 text-green-700">
                  <CheckCircle className="h-8 w-8" />
                  <div>
                    <div className="font-bold text-lg">Audit Chain Intact</div>
                    <div className="text-sm">{verification.events} events verified successfully.</div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3 text-red-700">
                  <AlertTriangle className="h-8 w-8" />
                  <div>
                    <div className="font-bold text-lg">Chain Broken!</div>
                    <div className="text-sm">Mismatch detected at event #{verification.first_broken_id}.</div>
                  </div>
                </div>
              )
            ) : (
              <div className="text-muted-foreground">Verifying integrity...</div>
            )}
          </CardContent>
        </Card>

        {/* Regulatory Policy Card */}
        <Card className="border-2 border-slate-200 shadow-sm relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10">
            <Scale className="h-24 w-24" />
          </div>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Scale className="h-5 w-5 text-slate-700" />
              Regulatory Policy
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 relative z-10">
            {policy ? (
              <div className="grid grid-cols-2 gap-y-4 text-sm">
                <div>
                  <div className="font-semibold text-slate-500">Jurisdiction</div>
                  <div className="font-medium">{policy.jurisdiction}</div>
                </div>
                <div>
                  <div className="font-semibold text-slate-500">Retention Period</div>
                  <div className="font-medium">{policy.retention_days} days</div>
                </div>
                <div className="col-span-2">
                  <div className="font-semibold text-slate-500">Lawful Basis</div>
                  <div className="font-medium">{policy.lawful_basis}</div>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-sm">Loading policy...</div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Event Log</CardTitle>
          <CardDescription>View detailed application events and structural modifications.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-4 mb-6">
            <div className="space-y-2 flex-1">
              <Label>Event Type</Label>
              <select 
                className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                value={eventType}
                onChange={e => setEventType(e.target.value)}
              >
                <option value="all">All Events</option>
                <option value="triage_assessment">Triage Assessment</option>
                <option value="clinician_override">Clinician Override</option>
                <option value="vitals_update">Vitals Update</option>
                <option value="visit_closed">Visit Closed</option>
              </select>
            </div>
            <div className="space-y-2 flex-1">
              <Label>Entity Type</Label>
              <Input 
                placeholder="e.g. Patient, Visit..." 
                value={entityType}
                onChange={e => setEntityType(e.target.value)}
              />
            </div>
            <div className="space-y-2 w-full md:w-32">
              <Label>Limit</Label>
              <select 
                className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                value={limit}
                onChange={e => setLimit(Number(e.target.value))}
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Event Type</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Purpose</TableHead>
                  <TableHead>Hash</TableHead>
                  <TableHead>Timestamp</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">Loading events...</TableCell></TableRow>
                ) : events?.length === 0 ? (
                  <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">No events found.</TableCell></TableRow>
                ) : (
                  events?.map((ev: any) => (
                    <React.Fragment key={ev.id}>
                      <TableRow className="cursor-pointer hover:bg-slate-50 transition-colors" onClick={() => toggleRow(ev.id)}>
                        <TableCell className="font-medium">{ev.id}</TableCell>
                        <TableCell><Badge variant="outline" className="bg-slate-100">{ev.event_type}</Badge></TableCell>
                        <TableCell>{ev.entity_type} {ev.entity_id && `#${ev.entity_id}`}</TableCell>
                        <TableCell>{ev.actor}</TableCell>
                        <TableCell className="max-w-[200px] truncate">{ev.purpose}</TableCell>
                        <TableCell className="font-mono text-xs text-slate-500" title={ev.event_hash}>
                          {ev.event_hash?.substring(0, 12)}...
                        </TableCell>
                        <TableCell className="whitespace-nowrap">{new Date(ev.created_at).toLocaleString()}</TableCell>
                      </TableRow>
                      {expandedRows[ev.id] && (
                        <TableRow className="bg-slate-50">
                          <TableCell colSpan={7} className="p-4">
                            <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-x-auto text-sm font-mono">
                              <pre>{JSON.stringify(ev.payload, null, 2)}</pre>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
