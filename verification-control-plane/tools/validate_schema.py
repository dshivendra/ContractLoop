import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from jsonschema import Draft202012Validator
from vcp.models import Contract
from vcp.reconciliation import reference_contract

schema=json.loads((ROOT/"CONTRACT_SCHEMA.json").read_text())
generated=Contract.model_json_schema()
generated["$schema"]="https://json-schema.org/draft/2020-12/schema"
if schema != generated:
    raise SystemExit("Committed CONTRACT_SCHEMA.json differs from current Contract model; regenerate and review it")
Draft202012Validator.check_schema(schema)
validator=Draft202012Validator(schema)
document=reference_contract().model_dump(mode="json")
validator.validate(document)
roundtrip=Contract.model_validate(document)
assert roundtrip == reference_contract()
invalid=dict(document,conditions=[])
assert list(validator.iter_errors(invalid))
print("Draft 2020-12 schema valid; reference and roundtrip pass; empty conditions rejected. Semantic validation remains in Pydantic/kernel.")
