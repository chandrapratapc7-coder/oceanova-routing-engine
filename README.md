# Oceanova Maritime Routing Engine 🚢🌊

An enterprise-grade, full-stack maritime routing and financial optimization platform. Oceanova bridges the gap between raw meteorological data and commercial shipping operations by calculating the exact financial and temporal impacts of ocean weather on vessel performance. 

By integrating an A* pathfinding algorithm, hydrodynamic physics, and live oceanographic data, the platform empowers vessel operators to make data-driven decisions on macro-corridor selection, storm avoidance, and Laycan contract compliance.

---

## 📑 Project Overview

Commercial shipping fleets lose millions of dollars annually to hydrodynamic drag caused by severe weather. Oceanova moves beyond standard distance-based routing by outputting direct financial ROI. 

The system evaluates primary routes against massive geographic detours (e.g., Suez Canal vs. Cape of Good Hope). It factors in Admiralty-formula bunker fuel burn, ECA (Emission Control Area) premiums, EU ETS CO₂ carbon taxes, and canal transit dues to identify the most **profitable and contractually compliant** path.

---

## ✨ Core Features

* **A* Pathfinding & Corridor Simulation:** Dynamically calculates optimized global shipping corridors, avoiding landmasses and navigating specific ECA zones using a custom backend grid.
* **Hydrodynamic Physics Engine:** Calculates the physical reduction of Speed Over Ground (SOG) compared to the commanded Speed Through Water (STW) based on wave direction and real-time sea states.
* **Dynamic Weather Visualization:** Renders interactive wind arrows, wave heights, and surface currents directly onto the map with a synchronized timeline playback scrubber.
* **Commercial ROI Dashboards:** Head-to-head financial comparisons between primary and detour routes, calculating the exact "Weather Risk Value" avoided in dollars.
* **Automated Laycan Compliance:** Monitors vessel ETA against strict contract deadlines and generates automated speed-increase recommendations to prevent late-arrival penalties.
* **Dynamic PDF Generation:** Client-side generation of standardized, compliant Master Voyage Orders ready for dispatch.

---

## 🛠️ Technical Stack

**Frontend Architecture**
* **Vanilla JavaScript:** Selected over heavy UI frameworks to ensure spatial rendering, DOM manipulation, and timeline scrubbing remain extremely fast and lightweight without overhead.
* **HTML5 & CSS3:** Responsive, custom-styled dashboard interface.
* **Google Maps API:** Utilized for robust spherical geometry calculations, advanced marker anchoring, and interactive polyline rendering to prevent Great Circle land-clipping over massive distances.

**Backend Architecture**
* **Python & FastAPI:** High-performance asynchronous API serving the core A* math engine.
* **Multi-threading & Memoization:** Utilizes `ThreadPoolExecutor` and `@lru_cache` to drastically reduce latency when aggregating live sequential data, dropping calculation times from 90+ seconds to under 3 seconds.
* **NOAA ERDDAP (OSCAR):** Integration for live, real-world oceanographic surface currents and meteorological data.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.8+
* A modern web browser
* A Google Maps API Key (with Maps JavaScript API enabled)

### Backend Setup (FastAPI)
1. Clone the repository:
```bash
   git clone [https://github.com/chandrapratapc7-coder/oceanova-routing-engine.git](https://github.com/chandrapratapc7-coder/oceanova-routing-engine.git)
   cd oceanova-routing-engine/backend
