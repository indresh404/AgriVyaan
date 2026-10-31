# AgriVyaan Swarm Visual Assets

This directory contains visual media assets utilized by the AgriVyaan Swarm Simulation and Replay Dashboard.

> **CRITICAL DISCLAIMER:**
> Simulation prototype only. Synthetic crop conditions, detections, and abstract energy model. Not real agricultural observations, certified flight controllers, or physical drone flight results.

## Visual Assets (Crop Imagery Only — Zero Satellite Imagery)

1. **`crop_image.png`**: High-resolution top-down aerial crop image representing the operational farm field surface with parallel potato crop rows and natural soil.
2. **`master_drone.png`**: Top-view transparent icon representing the primary coordinator / scout drone (Drone 0).
3. **`drone.png`**: Top-view transparent icon representing secondary swarm investigation drones (Drones 1 through 9).
4. **`crop_yellowish.jpeg`**: Crop visual evidence depicting nutrient deficiency / chlorosis (yellowing foliage).
5. **`crop_growth.jpeg`**: Crop visual evidence depicting stunted canopy growth, necrosis, and viral dwarfism (brown discolored foliage).
6. **`crop_early_blight.jpeg`**: Crop visual evidence depicting fungal blight infection (*Alternaria solani*).

## Mathematical Models & Specifications

### 1. Camera Footprint Formula
For downward-facing cameras with horizontal field-of-view $\theta_x = 65^\circ$ ($1.134\text{ rad}$) and vertical field-of-view $\theta_y = 50^\circ$ ($0.873\text{ rad}$) at flight height $h$ in metres above canopy:

$$\text{Footprint Width } (W_f) = 2 \cdot h \cdot \tan\left(\frac{\theta_x}{2}\right)$$
$$\text{Footprint Height } (H_f) = 2 \cdot h \cdot \tan\left(\frac{\theta_y}{2}\right)$$

When flight height increases, the ground footprint expands, and square scanning zones scale dynamically.

### 2. Square Scanning Zones
The farm field is partitioned into an $N \times M$ grid of square scanning zones. The size of each square zone $S$ is derived directly from the optical footprint with standard 15% overlap:

$$S \approx W_f \times (1 - 0.15)$$

### 3. Two-Stage Detection Architecture
- **Stage A (Master Scout Drone)**:
  - Sweeps square zones at high altitude ($20\text{m} - 45\text{m}$).
  - Detects **Yellowish** and **Brown (stunted growth)** foliage ONLY.
  - Flags candidate zones (`CANDIDATE` / `QUEUED_FOR_INSPECTION`).
  - Does NOT confirm disease diagnoses directly.
- **Stage B (Multi-Drone Detailed Investigation)**:
  - Investigation fleet deploys at lower inspection altitude ($8\text{m} - 15\text{m}$).
  - Performs close-up multispectral scanning over flagged candidates.
  - Confirms and classifies underlying disease pathology (Early Blight / Late Blight / Chlorosis).

### 4. Collision Avoidance & Battery Reserve
- Safe separation threshold: $6.0\text{m}$. Drones hold position (`WAITING_FOR_CLEAR_PATH`) if flight corridors conflict.
- Low-battery reserve threshold: $20\%$. Drones hit reserve release pending tasks and execute Return-to-Base (RTH) autonomously.
