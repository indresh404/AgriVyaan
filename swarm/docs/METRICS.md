# AgriVyaan Swarm Metrics Specification

> **Notice:** Simulation only — synthetic zones and an abstract energy model. Not real crop detections, not real flight or battery results.

This document formally defines every metric calculated and reported by `agrivyaan_swarm`.

---

## 1. Units of Measurement

| Physical Dimension | Simulation Unit | Symbol | Notes |
| :--- | :--- | :--- | :--- |
| **Distance** | Metres | $\text{m}$ | Field dimensions, coordinates, and flight trajectories |
| **Time** | Seconds | $\text{s}$ | Simulation clock, task inspection duration |
| **Velocity** | Metres per second | $\text{m/s}$ | Linear speed without overshoot |
| **Energy** | Energy Units | $\text{EU}$ | Abstract energy model (not Wh, not % of real battery) |

---

## 2. Core Performance Metrics

### 2.1 Mission Completion Time (Makespan)
- **Symbol:** $T_{\text{makespan}}$
- **Unit:** $\text{s}$
- **Definition:** Elapsed simulation time from mission start ($t = 0$) until the simulation reaches a terminal state (all drones landed at base with no pending work, all drones failed, or maximum time limit reached).
- **Calculation:** $t_{\text{end}} - t_{\text{start}}$

### 2.2 Total Distance Travelled
- **Symbol:** $D_{\text{total}}$
- **Unit:** $\text{m}$
- **Definition:** The cumulative Euclidean distance flown across all drones in the swarm.
- **Calculation:**
  $$D_{\text{total}} = \sum_{d \in \text{Drones}} D_d$$

### 2.3 Total Energy Consumed
- **Symbol:** $E_{\text{total}}$
- **Unit:** $\text{EU}$
- **Definition:** Total energy expended by all drones for locomotion and inspection activities.
- **Calculation:**
  $$E_{\text{total}} = \sum_{d \in \text{Drones}} E_d$$
  Where $E_d = E_{\text{travel}, d} + E_{\text{inspect}, d}$.

### 2.4 Energy Per Completed Task
- **Symbol:** $E_{\text{per\_task}}$
- **Unit:** $\text{EU / task}$
- **Definition:** Energy efficiency normalized against successful task completions.
- **Calculation:**
  $$E_{\text{per\_task}} = \begin{cases} \frac{E_{\text{total}}}{N_{\text{completed}}}, & \text{if } N_{\text{completed}} > 0 \\ 0.0, & \text{if } N_{\text{completed}} = 0 \end{cases}$$

### 2.5 Priority-Weighted Coverage
- **Symbol:** $C_{\text{priority}}$
- **Unit:** Dimensionless $\in [0.0, 1.0]$
- **Definition:** The fraction of total field priority successfully inspected.
- **Calculation:**
  $$C_{\text{priority}} = \frac{\sum_{k \in \text{Completed}} \text{priority}_k}{\sum_{k \in \text{All}} \text{priority}_k}$$
- **Fallback Rule:**
  - If $\sum_{k \in \text{All}} \text{priority}_k = 0$, falls back to unweighted completion ratio: $\frac{N_{\text{completed}}}{N_{\text{all}}}$.
  - If $N_{\text{all}} = 0$, reports `"n/a"`.

### 2.6 Load Balance
- **Symbol:** $\sigma_{\text{load}}$
- **Unit:** Tasks (standard deviation)
- **Definition:** Standard deviation of completed tasks across the drone fleet. A lower standard deviation indicates an even workload distribution.
- **Calculation:**
  $$\sigma_{\text{load}} = \sqrt{\frac{1}{|\text{Drones}| - 1} \sum_{d \in \text{Drones}} (N_{d} - \bar{N})^2}$$

---

## 3. Resilience and Fault Recovery Metrics

### 3.1 Failure Recovery Delay
- **Symbol:** $\Delta t_{\text{recovery}}$
- **Unit:** $\text{s}$
- **Definition:** For each task that was reassigned after a drone failure:
  $$\Delta t_{\text{recovery}} = t_{\text{reassigned}} - t_{\text{failure}}$$
- Reported as both **Mean** and **Max** recovery delay.

### 3.2 Tasks Completed After Reassignment
- **Symbol:** $N_{\text{reassigned\_completed}}$
- **Definition:** Count of tasks that were released due to drone failure and subsequently completed by another operational drone.

---

## 4. Critical Invariant Checks

The simulation validates two zero-tolerance physical invariants:

| Invariant | Valid Target | Meaning of Non-Zero Value |
| :--- | :--- | :--- |
| **Duplicate Assignments** | **0** | A task was assigned or executed concurrently or repeatedly. A non-zero value is treated as an algorithmic error. |
| **Battery Reserve Violations** | **0** | A drone exhausted energy below its reserved safety floor ($E_{\text{reserve}} = \text{fraction} \times \text{capacity}$). Non-zero indicates an invalid feasibility calculation. |
