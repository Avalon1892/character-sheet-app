"""Run the complete test suite with a fresh Qt process per test module.

Native Qt objects from unrelated test modules must not outlive each module's
QApplication fixture. Isolation also contains native crashes without skipping
the rest of the suite. Every module produces its own log and JUnit report.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers",type=int,default=2)
    parser.add_argument("--output",default="artifacts/isolated-suite")
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    output=(root/args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    modules=sorted((root/"tests").glob("test_*.py"))
    started=time.monotonic()
    env=dict(os.environ,QT_QPA_PLATFORM="offscreen")

    def run(module):
        report=output/(module.stem+".xml")
        command=[sys.executable,"-m","pytest",str(module),"-q",
                 "--junitxml="+str(report),"-o","faulthandler_timeout=300"]
        try:
            process=subprocess.run(command,cwd=root,env=env,capture_output=True,
                                   text=True,encoding="utf-8",errors="replace",timeout=1800)
            code=process.returncode;log=process.stdout+process.stderr
        except subprocess.TimeoutExpired as error:
            code=124;log="Test module exceeded 30 minutes.\n"+str(error)
        (output/(module.stem+".log")).write_text(log,encoding="utf-8")
        result={"module":module.name,"exit_code":code,"tests":0,"failures":0,"errors":0,"skipped":0}
        if report.exists():
            for suite in ET.parse(report).getroot().iter("testsuite"):
                for key in ("tests","failures","errors","skipped"):
                    result[key]+=int(suite.get(key,"0"))
        return result

    results=[]
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        futures=[pool.submit(run,module) for module in modules]
        for future in as_completed(futures):
            result=future.result();results.append(result)
            print(f"{len(results)}/{len(modules)} {'PASS' if result['exit_code']==0 else 'FAIL'} "
                  f"{result['module']} ({result['tests']} tests)",flush=True)
    combined=ET.Element("testsuites",name="Complete isolated test suite")
    for module in modules:
        report=output/(module.stem+".xml")
        if report.exists():
            for suite in ET.parse(report).getroot().iter("testsuite"):combined.append(suite)
    ET.ElementTree(combined).write(output/"complete.xml",encoding="utf-8",xml_declaration=True)
    summary={"modules":len(modules),"seconds":round(time.monotonic()-started,2),
             **{key:sum(r[key] for r in results) for key in ("tests","failures","errors","skipped")},
             "failed_modules":[r for r in results if r["exit_code"]!=0]}
    (output/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary),flush=True)
    return bool(summary["failed_modules"])


if __name__=="__main__":raise SystemExit(main())
