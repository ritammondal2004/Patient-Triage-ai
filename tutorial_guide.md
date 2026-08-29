# PatientTriage.ai — Frontend Tutorial & Verification Guide

This guide explains how to use every page of the **PatientTriage.ai Command Center** and provides test inputs so you can verify that the frontend and backend are communicating perfectly.

## 1. Dashboard (`/`)
**What it does:** The central command interface for the Emergency Department (ED). It shows a real-time overview of the waiting room, priority distribution, and AI Engine status.
- **P1 - P5 Cards:** Shows how many patients are currently waiting for each triage level. The P1 card pulses in red if there is a critical patient waiting.
- **Metrics:** Displays Total Waiting, Average Wait, Breaches (patients waiting beyond their safe threshold), and Reassessments Due.
- **Live Queue:** A preview of the 10 most urgent patients. 

**How to Verify:**
1. Check the **AI Engine Status** card on the right. It should display "Engine OK", "1.0.0-prototype", and the current safety mode.
2. If the ED is empty, the queue should say "Queue is currently empty." We will populate it in the next step.

---

## 2. Patient Intake (`/intake`)
**What it does:** The registration desk form where new arrivals are logged. This form submits data to the AI Engine for instant triage scoring.

**How to Verify (Test Scenario 1: High-Confidence P1):**
1. Navigate to **Patient Intake**.
2. **Demographics:** Age = `58`, Gender = `Male`. Leave Prior History unchecked.
3. **Presentation:** Chief Complaint = `cardiac_arrest` (or type "cardiac arrest" in the symptom box). Arrival Mode = `Ambulance`.
4. **Vitals:** Leave everything blank (to test how the model handles missing data), or enter HR = `0`, BP = `0`.
5. Click **▶ RUN TRIAGE ASSESSMENT**.

**Expected Output:**
- A Triage Result Card will appear below the form.
- **Priority Badge:** Should clearly state **P1 — CRITICAL** (Red).
- **Risk Probability:** Close to 99-100%.
- **Confidence:** Should show reasons for the decision.
- You can now click "Go to Queue" to see this patient in the live queue.

**How to Verify (Test Scenario 2: Safety Rule Override):**
1. Click **New Patient** to clear the form.
2. **Demographics:** Age = `8` (Pediatric case), Gender = `Female`.
3. **Presentation:** Chief Complaint = `fever`. Arrival = `Walk-in`.
4. **Vitals:** Temp = `40.5` °C.
5. Click **▶ RUN TRIAGE ASSESSMENT**.

**Expected Output:**
- The ML model might predict P3 (Standard), but a yellow **Safety Rules Triggered** banner will appear.
- The banner will explain that the AI was overridden from P3 to **P2 — URGENT** due to the rule: "Pediatric High Fever (Age < 12, Temp > 40.0)".

---

## 3. Queue (`/queue`)
**What it does:** The live ED waiting room management screen. Doctors and nurses use this to decide who to see next.

**How to Verify:**
1. Navigate to **Queue**. You should see the patients you just created.
2. The table is automatically sorted by Priority (P1s first), and then by longest wait time.
3. **Test "Call Next Patient":** Click the green button at the top right. 
   - **Expected Output:** A pop-up/card will tell you which patient to call (it should be your P1 patient). The patient will automatically transition to "in_treatment" and disappear from the waiting queue.
4. **Test "Discharge":** Click the red "Discharge" action on any patient row.
   - **Expected Output:** The patient is closed and removed from the queue.

---

## 4. Patients (`/patients`)
**What it does:** A historical directory of all patients who have ever visited the ED.

**How to Verify:**
1. Navigate to **Patients**.
2. You will see a table of registered patients.
3. **Expand a patient:** Click on a patient row. It will expand to show their Visit History.
4. **Expand a visit:** Click on a visit to see the **Assessment History**.
   - **Expected Output:** You should see exactly how the AI scored that visit, what the risk probability was, and what safety rules were applied. This proves the system is retaining data properly.

---

## 5. Overrides (`/overrides`)
**What it does:** Allows clinicians to overrule the AI's triage recommendation. Crucial for clinical safety and continuous model training.

**How to Verify:**
1. You will need an `Assessment ID`. Go to the **Queue** or **Patients** page and note the ID of an assessment (or look at the URL/network payload), or simply use the ID from the result card when you run an intake.
2. Navigate to **Overrides**.
3. **Form Inputs:**
   - Assessment ID = (An existing ID, e.g., `1` or `2`)
   - Clinician ID = `DR-SHARMA`
   - Clinician Role = `Attending`
   - Override Priority = Choose a different priority than the AI gave (e.g., if AI gave P3, choose Level 2).
   - Reason Code = `clinical_judgement`
   - Reason Text = "Patient looks visibly distressed, upgrading priority."
   - Check the acknowledgement box and click Submit.
4. **Expected Output:** The override will appear in the History table below, clearly showing whether the clinician escalated (↑) or de-escalated (↓) the priority.

---

## 6. Simulation (`/simulation`)
**What it does:** Runs "Digital Twin" simulations of the ED to see how the triage rules and AI perform under stress (like a mass casualty event or a busy Monday).

**How to Verify:**
1. Navigate to **Simulation**.
2. **Scenario:** Select "Busy Monday (1.5x Volume)".
3. **Hours:** Leave at 8.
4. Click **Run Simulation**. (Wait 10-20 seconds).
5. **Expected Output:** 
   - A beautiful dashboard will render below showing Wait Time by Priority (Bar chart).
   - It will show if the ED breached safe wait times.
   - It will show how many patients were saved by the "Reassessment" loop (e.g., patients who got worse while waiting and were automatically flagged).

---

## 7. Audit Trail (`/audit`)
**What it does:** The compliance engine. It proves to regulators (e.g., under the India DPDP Act or HIPAA) that the AI's decisions haven't been tampered with.

**How to Verify:**
1. Navigate to **Audit Trail**.
2. **Expected Output 1:** The big card at the top should say **"Chain Intact!"** in green. This means cryptographic hashes for every event match perfectly.
3. **Expected Output 2:** The Regulatory Policy card correctly cites the India DPDP Act and the retention period.
4. Scroll down to the Event Log. Click on an event (like `triage_assessment` or `clinician_override`).
   - It will expand to show the raw JSON payload, proving full transparency of what the AI saw and decided at that exact millisecond.
