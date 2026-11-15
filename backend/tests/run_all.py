"""Minimal runner for environments without pytest:  python tests/run_all.py"""
import importlib.util, os, sys, time, traceback
sys.path.insert(0, os.path.dirname(__file__))
fails = 0
for fname in sorted(f for f in os.listdir(os.path.dirname(__file__)) if f.startswith("test_") and f.endswith(".py")):
    spec = importlib.util.spec_from_file_location(fname[:-3], os.path.join(os.path.dirname(__file__), fname))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    for name in sorted(n for n in dir(m) if n.startswith("test_")):
        t = time.time()
        try:
            getattr(m, name)(); print(f"PASS {fname}::{name} ({time.time()-t:.1f}s)")
        except Exception:
            fails += 1; print(f"FAIL {fname}::{name}"); traceback.print_exc()
print("FAILED:", fails) if fails else print("ALL PASSED")
sys.exit(1 if fails else 0)
