"""Measure executable-line coverage of kernel tests and demo using CPython trace."""
import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import sys
import trace
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    tracer=trace.Trace(count=True,trace=False,ignoredirs=(sys.base_prefix,str(Path(os.__file__).parent)))
    def run():
        suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"),top_level_dir=str(ROOT))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        if result.wasSuccessful():
            with redirect_stdout(io.StringIO()):runpy.run_module("vcp",run_name="__main__")
        return result
    prior_thread_trace=threading.gettrace()
    threading.settrace(tracer.globaltrace)
    try:result=tracer.runfunc(run)
    finally:threading.settrace(prior_thread_trace)
    counts=tracer.results().counts;rows=[]
    for path in sorted((ROOT/"vcp").rglob("*.py")):
        # CPython's trace implementation provides executable source line discovery.
        executable=set(trace._find_executable_linenos(str(path)))
        covered={line for line in executable if counts.get((str(path),line),0)>0}
        rows.append(dict(path=str(path.relative_to(ROOT)),covered=len(covered),executable=len(executable),
                         missed_lines=sorted(executable-covered)))
    covered=sum(x["covered"] for x in rows);total=sum(x["executable"] for x in rows)
    report=dict(method="CPython trace; executable lines, not branch coverage",tests=result.testsRun,
                failures=len(result.failures),errors=len(result.errors),covered=covered,executable=total,
                percent=round(100*covered/total,2) if total else None,files=rows)
    (args.output/"coverage.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="files"}))
    return 0 if result.wasSuccessful() else 1


if __name__=="__main__":raise SystemExit(main())
