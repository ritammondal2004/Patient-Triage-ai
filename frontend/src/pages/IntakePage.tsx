import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useSubmitIntake } from '@/hooks/use-api';
import { cn, PRIORITY_CONFIG, CONFIDENCE_CONFIG } from '@/lib/utils';
import { AlertTriangle, ShieldAlert, ArrowRight, RotateCcw } from 'lucide-react';
import { Link } from 'react-router-dom';

const COMPLAINTS = [
  'chest_pain', 'abdominal_pain', 'shortness_of_breath', 'headache', 'trauma',
  'fever', 'seizure', 'cardiac_arrest', 'allergic_reaction', 'altered_consciousness',
  'back_pain', 'dizziness', 'nausea', 'laceration', 'fracture', 'stroke', 'bleeding', 'other'
].sort();

export const IntakePage = () => {
  const { mutate, isPending, data, error, reset } = useSubmitIntake();

  const [formData, setFormData] = useState({
    patient_code: '',
    age: '',
    gender: 'male',
    has_prior_history: false,
    prior_conditions_count: '',
    prior_ed_visits: '',
    chief_complaint: 'chest_pain',
    symptom_text: '',
    arrival_mode: 'walk-in',
    heart_rate: '',
    respiratory_rate: '',
    systolic_bp: '',
    diastolic_bp: '',
    temperature: '',
    spo2: '',
    pain_score: '0'
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      patient: {
        patient_code: formData.patient_code || undefined,
        age: parseInt(formData.age, 10),
        gender: formData.gender,
        has_prior_history: formData.has_prior_history,
        prior_conditions_count: formData.has_prior_history ? parseInt(formData.prior_conditions_count || '0', 10) : 0,
        prior_ed_visits: formData.has_prior_history ? parseInt(formData.prior_ed_visits || '0', 10) : 0,
      },
      chief_complaint: formData.chief_complaint,
      symptom_text: formData.symptom_text || undefined,
      arrival_mode: formData.arrival_mode,
      vitals: {
        heart_rate: formData.heart_rate ? parseInt(formData.heart_rate, 10) : undefined,
        respiratory_rate: formData.respiratory_rate ? parseInt(formData.respiratory_rate, 10) : undefined,
        systolic_bp: formData.systolic_bp ? parseInt(formData.systolic_bp, 10) : undefined,
        diastolic_bp: formData.diastolic_bp ? parseInt(formData.diastolic_bp, 10) : undefined,
        temperature: formData.temperature ? parseFloat(formData.temperature) : undefined,
        spo2: formData.spo2 ? parseInt(formData.spo2, 10) : undefined,
        pain_score: formData.pain_score ? parseInt(formData.pain_score, 10) : undefined,
      }
    };
    mutate(payload);
  };

  const handleReset = () => {
    setFormData({
      patient_code: '',
      age: '',
      gender: 'male',
      has_prior_history: false,
      prior_conditions_count: '',
      prior_ed_visits: '',
      chief_complaint: 'chest_pain',
      symptom_text: '',
      arrival_mode: 'walk-in',
      heart_rate: '',
      respiratory_rate: '',
      systolic_bp: '',
      diastolic_bp: '',
      temperature: '',
      spo2: '',
      pain_score: '0'
    });
    reset();
  };

  return (
    <div className="p-6 max-w-7xl mx-auto bg-slate-50 min-h-screen">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Patient Intake</h1>
        <p className="text-slate-500 mt-1">Enter patient details to run AI triage assessment</p>
      </div>

      <form onSubmit={handleSubmit} className="mb-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Column 1: Demographics */}
          <Card className="shadow-sm">
            <CardHeader className="bg-slate-100/50 border-b">
              <CardTitle className="text-lg">1. Demographics</CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Patient Code</label>
                <input type="text" name="patient_code" value={formData.patient_code} onChange={handleChange} placeholder="Auto-generated" className="w-full border rounded px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Age *</label>
                <input type="number" name="age" value={formData.age} onChange={handleChange} min="0" max="120" required className="w-full border rounded px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Gender</label>
                <select name="gender" value={formData.gender} onChange={handleChange} className="w-full border rounded px-3 py-2 text-sm">
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="flex items-center space-x-2 pt-2">
                <input type="checkbox" id="has_prior_history" name="has_prior_history" checked={formData.has_prior_history} onChange={handleChange} className="rounded text-blue-600 w-4 h-4" />
                <label htmlFor="has_prior_history" className="text-sm font-medium text-slate-700">Has Prior History</label>
              </div>
              {formData.has_prior_history && (
                <div className="space-y-4 pl-6 border-l-2 border-slate-200 mt-2">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Prior Conditions Count</label>
                    <input type="number" name="prior_conditions_count" value={formData.prior_conditions_count} onChange={handleChange} min="0" max="30" className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Prior ED Visits</label>
                    <input type="number" name="prior_ed_visits" value={formData.prior_ed_visits} onChange={handleChange} min="0" max="100" className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Column 2: Presentation */}
          <Card className="shadow-sm">
            <CardHeader className="bg-slate-100/50 border-b">
              <CardTitle className="text-lg">2. Presentation</CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Chief Complaint *</label>
                <select name="chief_complaint" value={formData.chief_complaint} onChange={handleChange} required className="w-full border rounded px-3 py-2 text-sm">
                  {COMPLAINTS.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Symptom Text</label>
                <textarea name="symptom_text" value={formData.symptom_text} onChange={handleChange} maxLength={1000} rows={4} className="w-full border rounded px-3 py-2 text-sm" placeholder="Describe symptoms..." />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Arrival Mode</label>
                <div className="space-y-2">
                  {['walk-in', 'ambulance', 'referred'].map(mode => (
                    <label key={mode} className="flex items-center space-x-2 text-sm">
                      <input type="radio" name="arrival_mode" value={mode} checked={formData.arrival_mode === mode} onChange={handleChange} className="text-blue-600" />
                      <span className="capitalize">{mode}</span>
                    </label>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Column 3: Vitals */}
          <Card className="shadow-sm">
            <CardHeader className="bg-slate-100/50 border-b flex justify-between items-center">
              <CardTitle className="text-lg">3. Vitals</CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <p className="text-xs text-slate-500 italic mb-2">All vitals optional. Missing values increase uncertainty.</p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Heart Rate</label>
                  <input type="number" name="heart_rate" value={formData.heart_rate} onChange={handleChange} placeholder="bpm" className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Resp Rate</label>
                  <input type="number" name="respiratory_rate" value={formData.respiratory_rate} onChange={handleChange} placeholder="/min" className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Systolic BP</label>
                  <input type="number" name="systolic_bp" value={formData.systolic_bp} onChange={handleChange} placeholder="mmHg" className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Diastolic BP</label>
                  <input type="number" name="diastolic_bp" value={formData.diastolic_bp} onChange={handleChange} placeholder="mmHg" className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Temp</label>
                  <input type="number" step="0.1" name="temperature" value={formData.temperature} onChange={handleChange} placeholder="°C" className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">SpO₂</label>
                  <input type="number" name="spo2" value={formData.spo2} onChange={handleChange} placeholder="%" className="w-full border rounded px-3 py-2 text-sm" />
                </div>
              </div>
              <div className="pt-2">
                <label className="block text-sm font-medium text-slate-700 mb-1 flex justify-between">
                  <span>Pain Score</span>
                  <span className="font-bold text-blue-600">{formData.pain_score}</span>
                </label>
                <input type="range" name="pain_score" value={formData.pain_score} onChange={handleChange} min="0" max="10" className="w-full" />
              </div>
            </CardContent>
          </Card>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
            Error submitting intake. Please check your inputs and try again.
          </div>
        )}

        <div className="mt-6">
          <button 
            type="submit" 
            disabled={isPending || !formData.age}
            className="w-full bg-blue-700 hover:bg-blue-800 text-white font-bold py-4 px-6 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center text-lg"
          >
            {isPending ? (
              <span className="animate-pulse">RUNNING ASSESSMENT...</span>
            ) : (
              <>▶ RUN TRIAGE ASSESSMENT</>
            )}
          </button>
        </div>
      </form>

      {/* Result Card */}
      {data && (
        <Card className="shadow-lg border-2 border-slate-200 overflow-hidden animate-in fade-in slide-in-from-bottom-4">
          <div className={cn(
            "text-white text-center py-4 text-3xl font-black",
            PRIORITY_CONFIG[data.assessment.final_priority]?.bg
          )}>
            P{data.assessment.final_priority} — {data.assessment.priority_label}
          </div>
          
          <CardContent className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-6">
              <div>
                <h3 className="text-sm font-bold text-slate-500 uppercase mb-2">Risk Assessment</h3>
                <div className="w-full bg-slate-200 rounded-full h-4 mb-2">
                  <div 
                    className={cn(
                      "h-4 rounded-full transition-all",
                      data.assessment.risk_probability > 0.7 ? "bg-red-500" : 
                      data.assessment.risk_probability > 0.4 ? "bg-orange-500" : "bg-teal-500"
                    )}
                    style={{ width: `${Math.min(Math.max(data.assessment.risk_probability * 100, 5), 100)}%` }}
                  ></div>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Risk Probability</span>
                  <span className="font-bold">{(data.assessment.risk_probability * 100).toFixed(1)}%</span>
                </div>
                
                <div className="mt-4">
                  <span className={cn(
                    "inline-block px-3 py-1 rounded-full text-sm font-bold",
                    CONFIDENCE_CONFIG[data.assessment.confidence_label]?.bg,
                    CONFIDENCE_CONFIG[data.assessment.confidence_label]?.color
                  )}>
                    {data.assessment.confidence_label} Confidence
                  </span>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-bold text-slate-500 uppercase mb-2">Risk Indicators</h3>
                <ul className="list-disc pl-5 text-sm space-y-1 text-slate-700">
                  {data.assessment.risk_indicators.length > 0 ? (
                    data.assessment.risk_indicators.map((ind: string, i: number) => <li key={i}>{ind}</li>)
                  ) : (
                    <li className="text-slate-400">No specific indicators identified</li>
                  )}
                </ul>

                {data.assessment.missing_fields && data.assessment.missing_fields.length > 0 && (
                  <div className="mt-4 text-sm text-red-600">
                    <span className="font-bold">Missing Fields: </span>
                    {data.assessment.missing_fields.join(', ')}
                  </div>
                )}
              </div>
            </div>

            {data.assessment.escalated_by_rules && (
              <div className="mb-4 bg-yellow-50 border border-yellow-200 rounded-md p-4 flex items-start">
                <ShieldAlert className="w-5 h-5 text-yellow-600 mr-3 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-bold text-yellow-800">Safety Rule Escalation</h4>
                  <p className="text-sm text-yellow-700 mt-1">
                    Escalated from P{data.assessment.ml_only_priority} to P{data.assessment.final_priority}: {data.assessment.safety_rules_triggered.join(', ')}
                  </p>
                </div>
              </div>
            )}

            {data.assessment.escalated_by_uncertainty && (
              <div className="mb-4 bg-amber-50 border border-amber-200 rounded-md p-4 flex items-start">
                <AlertTriangle className="w-5 h-5 text-amber-600 mr-3 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-bold text-amber-800">Uncertainty Escalation</h4>
                  <p className="text-sm text-amber-700 mt-1">
                    Priority elevated due to low confidence / high uncertainty.
                  </p>
                </div>
              </div>
            )}

            <div className="flex gap-4 mt-8 pt-6 border-t">
              <Link to="/queue" className="flex-1 bg-slate-900 hover:bg-slate-800 text-white text-center font-semibold py-3 px-4 rounded-md flex justify-center items-center">
                Go to Queue <ArrowRight className="w-4 h-4 ml-2" />
              </Link>
              <button onClick={handleReset} type="button" className="flex-1 bg-white border-2 border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold py-3 px-4 rounded-md flex justify-center items-center">
                <RotateCcw className="w-4 h-4 mr-2" /> New Patient
              </button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

