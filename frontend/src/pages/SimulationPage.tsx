import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Play, Loader2, Activity, Users, Clock, Bed, UserCheck } from 'lucide-react';
import { cn } from '@/lib/utils';

// Assume these are provided by the project's data layer
import { 
  useSimulationScenarios, 
  useRunSimulation, 
  useSimulationRuns, 
  useRunAblation, 
  useDayNight 
} from '@/hooks/use-api';

const PRIORITY_COLORS: Record<string, string> = {
  '1': '#DC2626',
  '2': '#EA580C',
  '3': '#D97706',
  '4': '#2563EB',
  '5': '#6B7280'
};

export function SimulationPage() {
  const { data: scenarios, isLoading: loadingScenarios } = useSimulationScenarios();
  const { data: pastRuns } = useSimulationRuns();
  const runSimulation = useRunSimulation();
  const runAblation = useRunAblation();
  const getDayNight = useDayNight();

  const [scenario, setScenario] = useState('');
  const [hours, setHours] = useState(8);
  const [seed, setSeed] = useState(42);

  const handleRun = () => {
    if (!scenario) return;
    runSimulation.mutate({ scenario, hours, seed, arrival_multiplier: 1.0, persist: true });
  };

  const handleAblation = () => {
    runAblation.mutate({ multiplier: 1.0, seed: 42, hours: 24 });
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">ED Surge Simulation</h1>
          <p className="text-muted-foreground">Model patient arrivals and evaluate operational performance.</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run Simulation</CardTitle>
          <CardDescription>Configure parameters for the next discrete event simulation run.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="scenario">Scenario</Label>
              <select 
                id="scenario"
                className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
              >
                <option value="" disabled>Select a scenario</option>
                {scenarios?.map((s: any) => (
                  <option key={s.name} value={s.name}>{s.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="hours">Duration (Hours: {hours})</Label>
              <input 
                id="hours"
                type="range" 
                min="1" 
                max="72" 
                value={hours} 
                onChange={(e) => setHours(parseInt(e.target.value))}
                className="w-full h-10"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="seed">Random Seed</Label>
              <Input 
                id="seed"
                type="number" 
                value={seed} 
                onChange={(e) => setSeed(parseInt(e.target.value))}
              />
            </div>
          </div>
        </CardContent>
        <CardFooter>
          <Button onClick={handleRun} disabled={runSimulation.isPending || !scenario} className="bg-[#1E40AF]">
            {runSimulation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Run Simulation
          </Button>
        </CardFooter>
      </Card>

      {runSimulation.data && (
        <div className="space-y-6">
          <h2 className="text-2xl font-semibold mt-8">Results Dashboard</h2>
          
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm font-medium text-muted-foreground flex items-center gap-2"><Users className="h-4 w-4"/> Arrivals</div>
                <div className="text-2xl font-bold mt-2">{runSimulation.data.metrics.arrivals}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm font-medium text-muted-foreground flex items-center gap-2"><UserCheck className="h-4 w-4"/> Treated</div>
                <div className="text-2xl font-bold mt-2">{runSimulation.data.metrics.treated}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm font-medium text-muted-foreground flex items-center gap-2"><Clock className="h-4 w-4"/> Mean Wait</div>
                <div className="text-2xl font-bold mt-2">{runSimulation.data.metrics.mean_wait_minutes.toFixed(1)}m</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm font-medium text-muted-foreground flex items-center gap-2"><Clock className="h-4 w-4"/> P90 Wait</div>
                <div className="text-2xl font-bold mt-2">{runSimulation.data.metrics.p90_wait_minutes.toFixed(1)}m</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm font-medium text-muted-foreground flex items-center gap-2"><Activity className="h-4 w-4"/> Doc Util</div>
                <div className="text-2xl font-bold mt-2">{(runSimulation.data.metrics.doctor_utilisation * 100).toFixed(1)}%</div>
                <div className="w-full bg-secondary h-2 mt-2 rounded-full overflow-hidden">
                  <div className="bg-[#0D9488] h-full" style={{width: `${runSimulation.data.metrics.doctor_utilisation * 100}%`}}></div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm font-medium text-muted-foreground flex items-center gap-2"><Bed className="h-4 w-4"/> Bed Util</div>
                <div className="text-2xl font-bold mt-2">{(runSimulation.data.metrics.bed_utilisation * 100).toFixed(1)}%</div>
                <div className="w-full bg-secondary h-2 mt-2 rounded-full overflow-hidden">
                  <div className="bg-[#0D9488] h-full" style={{width: `${runSimulation.data.metrics.bed_utilisation * 100}%`}}></div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="col-span-1 md:col-span-2">
              <CardHeader>
                <CardTitle>Wait Times by Priority</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={Object.entries(runSimulation.data.metrics.by_priority).map(([p, m]: any) => ({ priority: p, wait: m.mean_wait }))}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="priority" tickFormatter={(v) => `P${v}`} />
                      <YAxis label={{ value: 'Minutes', angle: -90, position: 'insideLeft' }} />
                      <Tooltip />
                      <Bar dataKey="wait" radius={[4, 4, 0, 0]}>
                        {Object.keys(runSimulation.data.metrics.by_priority).map((p) => (
                          <Cell key={`cell-${p}`} fill={PRIORITY_COLORS[p] || '#ccc'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
            
            <Card className="bg-[#0D9488]/10 border-[#0D9488]">
              <CardHeader>
                <CardTitle className="text-[#0D9488]">Caught by Reassessment</CardTitle>
                <CardDescription>Patients saved from deterioration by continuous monitoring loop.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-6xl font-black text-[#0D9488]">
                  {runSimulation.data.metrics.caught_by_reassessment}
                </div>
                <div className="mt-4 text-sm text-muted-foreground">
                  Escalations triggered: {runSimulation.data.metrics.escalations}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">
                  Total reassessments: {runSimulation.data.metrics.reassessments}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Priority Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Priority</TableHead>
                    <TableHead>Treated</TableHead>
                    <TableHead>Mean Wait</TableHead>
                    <TableHead>P90 Wait</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Within Target</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(runSimulation.data.metrics.by_priority).map(([p, m]: any) => (
                    <TableRow key={p}>
                      <TableCell><Badge style={{backgroundColor: PRIORITY_COLORS[p]}}>P{p}</Badge></TableCell>
                      <TableCell>{m.treated}</TableCell>
                      <TableCell>{m.mean_wait.toFixed(1)}m</TableCell>
                      <TableCell>{m.p90_wait.toFixed(1)}m</TableCell>
                      <TableCell>{m.target_minutes}m</TableCell>
                      <TableCell>{(m.within_target_pct * 100).toFixed(1)}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex gap-4">
        <Button variant="outline" onClick={handleAblation} disabled={runAblation.isPending}>
          {runAblation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Run Ablation Study (Reassessment Impact)
        </Button>
        <Button variant="outline" onClick={() => getDayNight.refetch()} disabled={getDayNight.isFetching}>
          {getDayNight.isFetching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Day/Night Contrast
        </Button>
      </div>

      {runAblation.data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
           <Card>
              <CardHeader><CardTitle>Reassessment ON</CardTitle></CardHeader>
              <CardContent>
                 Mean Wait: {runAblation.data.on.mean_wait.toFixed(1)}m<br/>
                 Adverse Events: {runAblation.data.on.adverse_events}
              </CardContent>
           </Card>
           <Card>
              <CardHeader><CardTitle>Reassessment OFF</CardTitle></CardHeader>
              <CardContent>
                 Mean Wait: {runAblation.data.off.mean_wait.toFixed(1)}m<br/>
                 Adverse Events: {runAblation.data.off.adverse_events}
              </CardContent>
           </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Past Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Scenario</TableHead>
                <TableHead>Multiplier</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pastRuns?.map((run: any) => (
                <TableRow key={run.id}>
                  <TableCell className="font-medium">{run.id}</TableCell>
                  <TableCell>{run.scenario}</TableCell>
                  <TableCell>{run.arrival_multiplier}x</TableCell>
                  <TableCell>{new Date(run.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
