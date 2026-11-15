# NASA Moon model

`moon.glb` is NASA Goddard Scientific Visualization Studio's Moon 3D model, built with imagery and topographic data from the Lunar Reconnaissance Orbiter (LRO).

- Source: https://svs.gsfc.nasa.gov/14959/
- Credit: NASA's Goddard Space Flight Center; model data provider Ernie Wright (USRA), as listed on the NASA SVS item page.
- `moon.glb` is the preserved 51.4 MB source model. The app uses `moon-optimized.glb`, a 4.6 MB visual export with reduced mesh density and a resized JPEG texture. Its mesh is simplified for display performance; it is not a measurement-grade terrain model.
- Regenerate the display export with `python scripts/optimize_moon_model.py` from the frontend directory. The script requires NumPy and Pillow and never modifies the source model.

The mission-site scores and many other values displayed by this educational app are still illustrative samples; the model does not make those values NASA-derived.
