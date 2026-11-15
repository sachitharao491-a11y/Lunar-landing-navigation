Standalone 3D Moon demo (sample mission data, no backend). Start a local server from the project root:

    python -m http.server 8000

Then open http://localhost:8000/standalone-demo/lunar-moon-navigator-demo.html.
The NASA LRO model is in ../frontend/assets/moon.glb (51.4 MB). Three.js and its GLTF loader need internet access (cdnjs/jsDelivr). The full-stack app is one folder up (see ../README.md).
