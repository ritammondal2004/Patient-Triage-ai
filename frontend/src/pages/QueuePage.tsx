import React, { useState, useEffect } from 'react';
import { useQueue, useQueueSummary, useCallNext, useCloseVisit, useReassessAll } from '@/hooks/use-api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { cn, PRIORITY_CONFIG, CONFIDENCE_CONFIG, formatWait } from '@/lib/utils';
import { Clock, AlertTriangle, Activity, RefreshCw, Play, CheckCircle } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';

export function QueuePage() {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const { data: queue, isLoading, isError } = useQueue();
  const { data: summary } = useQueueSummary();
  
  const queryClient = useQueryClient();
  
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["queueSummary"] });
    }, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, queryClient]);

  const callNext = useCallNext();
  const closeVisit = useCloseVisit();
  const reassessAll = useReassessAll();

  const handleCallNext = () => {
    callNext.mutate();
  };

  const handleDischarge = (visitId: number) => {
    if (window.confirm('Are you sure you want to discharge this patient?')) {
      closeVisit.mutate({ visitId, status: 'discharged' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Live ED Queue</h1>
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={cn(autoRefresh && 'bg-blue-50 text-blue-700')}
          >
            <RefreshCw className={cn("mr-2 h-4 w-4", autoRefresh && "animate-spin")} />
            Auto-refresh
          </Button>
          <Button onClick={() => reassessAll.mutate()} disabled={reassessAll.isPending} variant="secondary">
            <Activity className="mr-2 h-4 w-4" />
            Reassess All
          </Button>
          <Button onClick={handleCallNext} disabled={callNext.isPending} className="bg-teal-600 hover:bg-teal-700">
            <Play className="mr-2 h-4 w-4" />
            Call Next Patient
          </Button>
        </div>
      </div>

      {callNext.isSuccess && callNext.data && (
        <Card className="bg-teal-50 border-teal-200">
          <CardContent className="pt-6 flex items-center justify-between">
            <div className="flex items-center">
              <CheckCircle className="text-teal-600 h-6 w-6 mr-4" />
              <div>
                <p className="text-lg font-medium text-teal-900">Called Next Patient: {callNext.data.patient_code}</p>
                <p className="text-teal-700">Priority: {callNext.data.priority_label}</p>
              </div>
            </div>
            <Button variant="outline" onClick={() => callNext.reset()}>Dismiss</Button>
          </CardContent>
        </Card>
      )}

      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Waiting</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.waiting}</div>
            </CardContent>
          </Card>
          <Card className={cn(summary.wait_breaches > 0 && "bg-red-50 border-red-200")}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Wait Breaches</CardTitle>
              <AlertTriangle className={cn("h-4 w-4", summary.wait_breaches > 0 ? "text-red-600" : "text-muted-foreground")} />
            </CardHeader>
            <CardContent>
              <div className={cn("text-2xl font-bold", summary.wait_breaches > 0 && "text-red-600")}>{summary.wait_breaches}</div>
            </CardContent>
          </Card>
          <Card className={cn(summary.reassessments_due > 0 && "bg-amber-50 border-amber-200")}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Reassessments Due</CardTitle>
              <Clock className={cn("h-4 w-4", summary.reassessments_due > 0 ? "text-amber-600" : "text-muted-foreground")} />
            </CardHeader>
            <CardContent>
              <div className={cn("text-2xl font-bold", summary.reassessments_due > 0 && "text-amber-600")}>{summary.reassessments_due}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Longest Wait</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatWait(summary.longest_wait_minutes)}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Priority</TableHead>
                <TableHead>Patient</TableHead>
                <TableHead>Age</TableHead>
                <TableHead>Complaint</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Wait</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Alerts</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow><TableCell colSpan={9} className="text-center py-8">Loading queue...</TableCell></TableRow>
              ) : queue?.length === 0 ? (
                <TableRow><TableCell colSpan={9} className="text-center py-8">No patients in queue.</TableCell></TableRow>
              ) : (
                queue?.map((entry) => (
                  <TableRow key={entry.visit_id}>
                    <TableCell>
                      <Badge style={{ backgroundColor: PRIORITY_CONFIG[entry.final_priority]?.bg, color: PRIORITY_CONFIG[entry.final_priority]?.color }}>
                        {entry.priority_label}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium">{entry.patient_code}</TableCell>
                    <TableCell>{entry.age}</TableCell>
                    <TableCell>{entry.chief_complaint}</TableCell>
                    <TableCell>{entry.arrival_mode}</TableCell>
                    <TableCell className={cn(entry.wait_breached && "text-red-600 font-bold")}>
                      {formatWait(entry.waited_minutes)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" style={{ backgroundColor: CONFIDENCE_CONFIG[entry.confidence_label]?.bg, color: CONFIDENCE_CONFIG[entry.confidence_label]?.color, borderColor: CONFIDENCE_CONFIG[entry.confidence_label]?.color }}>
                        {entry.confidence_label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2 flex-wrap">
                        {entry.wait_breached && <Badge variant="destructive" className="text-[10px] uppercase">⚠ Breached</Badge>}
                        {entry.reassessment_due && <Badge variant="outline" className="text-[10px] uppercase border-amber-500 text-amber-700 bg-amber-50">Due</Badge>}
                        {entry.override_applied && <Badge variant="secondary" className="text-[10px] uppercase bg-purple-100 text-purple-700 hover:bg-purple-200">Overridden</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" asChild>
                        <a href={`/overrides?visit=${entry.visit_id}`}>Override</a>
                      </Button>
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700 hover:bg-red-50" onClick={() => handleDischarge(entry.visit_id)}>
                        Discharge
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
