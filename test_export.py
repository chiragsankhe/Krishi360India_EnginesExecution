"""Integration test, synthetic records kept under temporary storage only."""
import json,subprocess,tempfile
from pathlib import Path
from test_engines import Engines
from client import prepare,read_xlsx
base=Path(__file__).resolve().parent
t=Engines(); t.setUp()
old,new,h=t.client_fixture()
prepared=t.p/'prepared.json'; output=t.p/'SYNTHETIC_TEST_ONLY.xlsx'
payload=prepare(old,new,'UUID',prepared)
node='/Users/aj/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
subprocess.run([node,str(base/'exporter.mjs'),str(prepared),str(output)],check=True)
actual=read_xlsx(output,'Client Output')
expected=payload['sheets']['Client Output']
assert actual==expected,'Source data/header round trip mismatch'
assert len(actual)==88 and len(actual[0])==37
print(json.dumps({'integration':'PASS','synthetic_only':True,'records':87,'headings':37,'exact_roundtrip':True,'preview_directory':str(t.p)}))
# Copy previews only to internal work folder for visual QA.
dest=base.parents[1]/'.work'/'krishi360_execution_export_qa'; dest.mkdir(exist_ok=True)
for p in t.p.glob('*.png'): (dest/p.name).write_bytes(p.read_bytes())
(base/'actual_outputs'/'excel_export_test.json').write_text(json.dumps({'result':'PASS','fixture':'SYNTHETIC ONLY','rows':87,'literal_header_count':37,'exact_cell_roundtrip':True,'client_data_validated':False},indent=2))
t.tearDown()
