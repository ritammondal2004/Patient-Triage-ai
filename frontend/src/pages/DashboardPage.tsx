import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Clock, AlertTriangle, RefreshCw, Activity, Server, Shield, Brain } from 'lucide-react';
import { useQueue, useQueueSummary, useEngineInfo } from '@/hooks/use-api';
import { cn, PRIORITY_CONFIG, CONFIDENCE_CONFIG, formatWait } from '@/lib/utils';
import type { QueueEntryOut } from '@/types/api';
import { Link } from 'react-router-dom';

export const DashboardPage = () => {
  const { data: summary } = useQueueSummary();
  const { data: queue } = useQueue();
  const { data: engine } = useEngineInfo();

  const renderPriorityCards = () => {
    if (!summary) return null;
    return (
      <div className="grid grid-cols-5 gap-4 mb-6">
        {[1, 2, 3, 4, 5].map((p) => {
          const config = PRIORITY_CONFIG[p];
          const count = summary.by_priority[p.toString()] || 0;
          return (
            <Card 
              key={p} 
              className={cn(
                "border-l-4 shadow-sm",
                config?.border,
                p === 1 && count > 0 ? "animate-pulse border-red-600 bg-red-50/50" : ""
              )}
            >
              <CardContent className="p-4 flex flex-col items-center justify-center">
                <div className={cn("text-lg font-bold", config?.color)}>
                  P{p} - {config?.label}
                </div>
                <div className="text-4xl font-black mt-2">{count}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    );
  };

  const renderMetrics = () => {
    if (!summary) return null;
    return (
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-slate-500">Total Waiting</CardTitle>
            <Users className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.waiting}</div>
          </CardContent>
        </Card>
        
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-slate-500">Avg Wait Time</CardTitle>
            <Clock className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatWait(summary.average_wait_minutes)}</div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-slate-500">Wait Breaches</CardTitle>
            <AlertTriangle className={cn("h-4 w-4", summary.wait_breaches > 0 ? "text-red-500" : "text-slate-400")} />
          </CardHeader>
          <CardContent>
            <div className={cn("text-2xl font-bold", summary.wait_breaches > 0 && "text-red-600")}>
              {summary.wait_breaches}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-slate-500">Reassessments Due</CardTitle>
            <RefreshCw className={cn("h-4 w-4", summary.reassessments_due > 0 ? "text-amber-500" : "text-slate-400")} />
          </CardHeader>
          <CardContent>
            <div className={cn("text-2xl font-bold", summary.reassessments_due > 0 && "text-amber-600")}>
              {summary.reassessments_due}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  return (
    <div className="p-6 bg-slate-50 min-h-screen">
      <div className="mb-6 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">ED Command Center</h1>
          <p className="text-slate-500 mt-1">Live patient triage & queue monitoring</p>
        </div>
      </div>

      {renderPriorityCards()}
      {renderMetrics()}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <Card className="shadow-sm h-full">
            <CardHeader className="flex flex-row items-center justify-between border-b pb-4">
              <CardTitle className="text-lg font-semibold flex items-center">
                <Activity className="w-5 h-5 mr-2 text-blue-600" />
                Live Queue Preview
              </CardTitle>
              <Link to="/queue" className="text-sm text-blue-600 font-medium hover:underline">
                View Full Queue →
              </Link>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 text-slate-500 text-xs uppercase font-semibold">
                    <tr>
                      <th className="px-4 py-3">Prio</th>
                      <th className="px-4 py-3">Patient</th>
                      <th className="px-4 py-3">Complaint</th>
                      <th className="px-4 py-3">Wait</th>
                      <th className="px-4 py-3">Conf</th>
                      <th className="px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {queue?.slice(0, 10).map((p: QueueEntryOut) => (
                      <tr key={p.visit_id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3">
                          <span className={cn(
                            "inline-flex items-center justify-center w-8 h-8 rounded-full font-bold text-white",
                            PRIORITY_CONFIG[p.final_priority]?.bg
                          )}>
                            P{p.final_priority}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-medium text-slate-900">
                          {p.patient_code}
                          <div className="text-xs text-slate-500">{p.age}y</div>
                        </td>
                        <td className="px-4 py-3 truncate max-w-[150px]" title={p.chief_complaint}>
                          {p.chief_complaint.replace('_', ' ')}
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn("font-medium", p.wait_breached && "text-red-600 font-bold")}>
                            {p.waited_minutes}m
                          </span>
                          <div className="text-xs text-slate-400">max {p.max_wait_minutes}m</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn(
                            "px-2 py-1 rounded text-xs font-semibold",
                            CONFIDENCE_CONFIG[p.confidence_label]?.bg,
                            CONFIDENCE_CONFIG[p.confidence_label]?.color
                          )}>
                            {p.confidence_label}
                          </span>
                        </td>
                        <td className="px-4 py-3 flex gap-1">
                          {p.wait_breached && <AlertTriangle className="w-4 h-4 text-red-500" />}
                          {p.reassessment_due && <RefreshCw className="w-4 h-4 text-amber-500" />}
                        </td>
                      </tr>
                    ))}
                    {!queue?.length && (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                          Queue is currently empty.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="col-span-1">
          <Card className="shadow-sm">
            <CardHeader className="border-b pb-4">
              <CardTitle className="text-lg font-semibold flex items-center">
                <Brain className="w-5 h-5 mr-2 text-indigo-600" />
                AI Engine Status
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {engine ? (
                <>
                  <div className="flex justify-between items-center pb-2 border-b border-slate-100">
                    <span className="text-slate-500 flex items-center"><Server className="w-4 h-4 mr-2" />Version</span>
                    <span className="font-medium font-mono text-sm">1.0.0-prototype</span>
                  </div>
                  <div className="flex justify-between items-center pb-2 border-b border-slate-100">
                    <span className="text-slate-500 flex items-center"><Activity className="w-4 h-4 mr-2" />Status</span>
                    <span className="flex items-center text-teal-600 font-medium">
                      <span className="w-2 h-2 rounded-full bg-teal-500 mr-2 animate-pulse"></span>
                      {engine.status}
                    </span>
                  </div>
                  <div className="flex justify-between items-center pb-2 border-b border-slate-100">
                    <span className="text-slate-500 flex items-center"><Shield className="w-4 h-4 mr-2" />Safety Mode</span>
                    <span className="font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded">{engine.safety_mode}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Operating Thresh</span>
                    <span className="font-medium">{engine.operating_threshold}%</span>
                  </div>
                </>
              ) : (
                <div className="text-center py-4 text-slate-400">Loading engine info...</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

