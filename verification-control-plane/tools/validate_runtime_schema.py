"""Reject drift in the runtime's committed JSON schemas."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from vcp.runtime_models import Attestation,Composition,ExecutionContract
from jsonschema import Draft202012Validator


def schemas():
    for name,model in [('EXECUTION_SCHEMA.json',ExecutionContract),('ATTESTATION_SCHEMA.json',Attestation),('COMPOSITION_SCHEMA.json',Composition)]:
        schema=model.model_json_schema();schema['$schema']='https://json-schema.org/draft/2020-12/schema'
        yield name,schema


def main():
    for name,schema in schemas():
        Draft202012Validator.check_schema(schema)
        if json.loads((ROOT/name).read_text())!=schema:raise ValueError('runtime schema drift: '+name)
    print('3 runtime schemas valid and synchronized')


if __name__=='__main__':main()
