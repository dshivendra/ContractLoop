#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parent
def load(name): return json.loads((root/name).read_text())
g=load('graph/system_graph.json'); ids=[x['id'] for x in g['nodes']]
assert len(ids)==len(set(ids))
known=set(ids)
for e in g['edges']: assert e['from'] in known and e['to'] in known, e
s=load('catalog/skills.json'); a=load('catalog/agents.json'); l=load('catalog/layers.json')
assert len(s)==694 and len(a)==567
assert sum(x['skill_count'] for x in l['layers'])==694
assert len(load('contracts/layer-handoffs.json')['phases'])==7
print(f"Graph package structurally valid: {len(ids)} nodes, {len(g['edges'])} edges, 694 skills, 567 agent rows, 7 contracts.")

workflow=json.loads((root/'workflows/change-delivery.json').read_text())
registry=json.loads((root/'subagents/registry-and-bindings.json').read_text())
known_agents={x['agent_id'] for x in registry['agents']}
assert len(registry['agents'])==567 and len(known_agents)==567
assert len(registry['skill_bindings'])==694
assert all(x['execution_agent_id'] in known_agents for x in registry['skill_bindings'] if x['execution_agent_id'])
assert all(set(x['candidate_agent_ids']) <= known_agents for x in registry['skill_bindings'])
assert registry['curation_status']['catalog_owned_independent_skills']==497
assert registry['curation_status']['phase_skills_with_candidate_pools']==197
assert len(workflow['steps'])==9
print(f"Orchestration valid: {len(workflow['steps'])} steps, {len(registry['agents'])} agents, {len(registry['skill_bindings'])} skill bindings.")
