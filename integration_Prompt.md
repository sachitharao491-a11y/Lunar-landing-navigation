# NASA Data Integration Instructions

I am building a Lunar Landing Site Analysis application.

My backend uses Python and FastAPI, and my frontend uses React and TypeScript.

I want to integrate the following NASA/JPL data sources:

1. JPL Horizons API:
   - Retrieve Sun and Earth positions for a selected lunar landing site and date/time.
   - Convert the results into useful azimuth and elevation measurements.
   - Clearly document coordinate frames and time conventions.

2. NASA SPICE using SpiceyPy:
   - Integrate SPICE kernels for accurate celestial geometry.
   - Implement coordinate transformations.
   - Handle missing kernels and invalid inputs gracefully.

3. LOLA terrain datasets:
   - Investigate suitable lunar elevation datasets.
   - Implement a method to read elevation data.
   - Prepare for terrain horizon and obstruction calculations.

Development rules:
- Integrate one source at a time.
- Do not invent or hardcode NASA data.
- Clearly label mock data.
- Keep all data processing in the backend.
- Create reusable service modules.
- Add error handling and tests.
- Document the source, units, coordinate frames and assumptions.
- Do not claim terrain-aware visibility until terrain obstruction calculations are implemented.

Start with JPL Horizons only. Explain the architecture and implement the integration before moving to the next source.