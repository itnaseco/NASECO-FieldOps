#!/usr/bin/env python3
"""Generate the executive FieldOps process overview document.

The generated Markdown is intentionally presentation-friendly, but its
revision, capability snapshot, and source inventory are refreshed from the app
metadata whenever this script is run.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "naseco_fieldopsbackend" / "naseco_fieldopsbackend" / "doctype"
DOC_PATH = ROOT / "docs" / "executive_fieldops_process_overview.md"
STATE_PATH = ROOT / "docs" / ".executive_fieldops_process_overview_state.json"
API_PATH = ROOT / "naseco_fieldopsbackend" / "api.py"
HOOKS_PATH = ROOT / "naseco_fieldopsbackend" / "hooks.py"
RETIRED_DOCTYPES = {"Finding", "Finding Photo", "Visit Finding"}


PROCESS_GROUPS = {
	"Grower and land master data": {
		"Outgrower",
		"Farm Plot",
		"Plot Vertex",
		"Plot Photo",
		"Plot Crop Assignment",
		"Region",
	},
	"Crop planning and agronomy": {
		"Crop",
		"Crop Variety",
		"Season",
		"Crop Recipe",
		"Recipe Stage",
		"Recipe Input Item",
		"Crop Cycle",
		"Crop Cycle Stage",
		"Agronomy Activity Template",
		"Stage Activity",
	},
	"Season planning and command control": {
		"Season Production Plan",
		"Season Production Target",
		"Season Input Requirement",
		"Season Resource Allocation",
		"Season Milestone",
		"Season Readiness Item",
	},
	"Contract and commercial governance": {
		"Outgrower Production Contract",
		"Production Contract Template",
		"Production Contract Signatory",
		"Outgrower Pricing Policy",
		"Outgrower Pricing Band",
		"Crop Production Lot",
	},
	"Field execution and inspection": {
		"Field Visit",
		"Visit Type",
		"Visit Photo",
		"Inspection",
		"Inspection Template",
		"Inspection Parameter",
		"Inspection Standard",
		"Inspection Attribute",
		"Inspection Take",
		"Inspection Take Result",
		"Inspection Result",
		"Field Corrective Action",
		"Seed Harvest Quality Assessment",
	},
	"Inputs, advances, harvest, and settlement": {
		"Stage Input Request",
		"Stage Input Request Item",
		"Stage Input Dispatch",
		"Crop Cycle Advance Request",
		"Crop Cycle Harvest Receipt",
		"Crop Cycle Settlement",
		"Crop Cycle Settlement Adjustment",
		"Crop Cycle Settlement Cash Advance",
		"Crop Cycle Settlement Stock Input",
		"Crop Cycle Settlement Pricing Line",
		"FieldOps Settings",
	},
	"Mobile sync and controls": {
		"Sync Log",
		"Sync Conflict",
	},
}


@dataclass(frozen=True)
class DocTypeInfo:
	name: str
	module: str
	istable: bool
	field_count: int
	link_targets: tuple[str, ...]


def run_git(args: list[str]) -> str:
	try:
		return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
	except Exception:
		return "unavailable"


def load_doctypes() -> list[DocTypeInfo]:
	doctypes: list[DocTypeInfo] = []
	for path in sorted(DOCTYPE_ROOT.glob("*/*.json")):
		try:
			data = json.loads(path.read_text())
		except json.JSONDecodeError:
			continue
		name = data.get("name") or data.get("doctype") or path.parent.name.replace("_", " ").title()
		if name in RETIRED_DOCTYPES:
			continue
		fields = data.get("fields", [])
		link_targets = sorted(
			{
				field.get("options")
				for field in fields
				if field.get("fieldtype") in {"Link", "Table"} and field.get("options")
			}
		)
		doctypes.append(
			DocTypeInfo(
				name=name,
				module=data.get("module") or "",
				istable=bool(data.get("istable")),
				field_count=len(fields),
				link_targets=tuple(link_targets),
			)
		)
	return doctypes


def parse_api_store_mappings() -> dict[str, str]:
	if not API_PATH.exists():
		return {}
	mapping: dict[str, str] = {}
	tree = ast.parse(API_PATH.read_text())
	for node in tree.body:
		if isinstance(node, ast.Assign):
			targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
			if "BASE_STORE_TO_DOCTYPE" in targets and isinstance(node.value, ast.Dict):
				mapping.update(ast.literal_eval(node.value))
		elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
			call = node.value
			if (
				isinstance(call.func, ast.Attribute)
				and call.func.attr == "update"
				and isinstance(call.func.value, ast.Name)
				and call.func.value.id == "STORE_TO_DOCTYPE"
				and call.args
				and isinstance(call.args[0], ast.Dict)
			):
				mapping.update(ast.literal_eval(call.args[0]))
	return mapping


def parse_doc_events() -> dict[str, list[str]]:
	if not HOOKS_PATH.exists():
		return {}
	content = HOOKS_PATH.read_text()
	events: dict[str, list[str]] = {}
	for doctype in ("Stock Entry", "Payment Entry", "Purchase Receipt", "Purchase Invoice"):
		block_match = re.search(rf'"{re.escape(doctype)}":\s*\{{(?P<body>.*?)\n\t\}}', content, re.S)
		if not block_match:
			continue
		events[doctype] = re.findall(r'"([^"]+)":\s*"naseco_fieldopsbackend\.[^"]+"', block_match.group("body"))
	return events


def categorized_doctypes(doctypes: list[DocTypeInfo]) -> dict[str, list[DocTypeInfo]]:
	by_name = {doctype.name: doctype for doctype in doctypes}
	categories: dict[str, list[DocTypeInfo]] = {}
	assigned: set[str] = set()
	for group, names in PROCESS_GROUPS.items():
		items = [by_name[name] for name in sorted(names) if name in by_name]
		categories[group] = items
		assigned.update(item.name for item in items)
	other = [doctype for doctype in doctypes if doctype.name not in assigned]
	if other:
		categories["Other app objects"] = sorted(other, key=lambda item: item.name)
	return categories


def build_snapshot(doctypes: list[DocTypeInfo], api_mappings: dict[str, str], doc_events: dict[str, list[str]]) -> dict:
	categories = categorized_doctypes(doctypes)
	return {
		"doctype_count": len(doctypes),
		"parent_doctype_count": sum(1 for item in doctypes if not item.istable),
		"child_table_count": sum(1 for item in doctypes if item.istable),
		"api_mapping_count": len(api_mappings),
		"erpnext_event_doctypes": sorted(doc_events),
		"categories": {
			group: [item.name for item in items]
			for group, items in categories.items()
		},
		"source_files": sorted(
			str(path.relative_to(ROOT))
			for path in [
				*DOCTYPE_ROOT.glob("*/*.json"),
				API_PATH,
				HOOKS_PATH,
			]
			if path.exists()
		),
	}


def stable_fingerprint(snapshot: dict) -> str:
	payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
	return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_state() -> dict:
	if not STATE_PATH.exists():
		return {"revision": 0, "fingerprint": ""}
	try:
		return json.loads(STATE_PATH.read_text())
	except json.JSONDecodeError:
		return {"revision": 0, "fingerprint": ""}


def write_state(revision: int, fingerprint: str, updated_display: str) -> None:
	STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
	STATE_PATH.write_text(
		json.dumps(
			{
				"revision": revision,
				"fingerprint": fingerprint,
				"updated_at": datetime.now().isoformat(timespec="seconds"),
				"updated_display": updated_display,
			},
			indent=2,
			sort_keys=True,
		)
		+ "\n"
	)


def summarize_names(items: list[DocTypeInfo], limit: int = 8) -> str:
	if not items:
		return "-"
	names = [item.name for item in items]
	if len(names) <= limit:
		return ", ".join(names)
	return ", ".join(names[:limit]) + f", plus {len(names) - limit} more"


def render_document(
	doctypes: list[DocTypeInfo],
	api_mappings: dict[str, str],
	doc_events: dict[str, list[str]],
	revision: int,
	fingerprint: str,
	updated: str,
) -> str:
	categories = categorized_doctypes(doctypes)
	commit = run_git(["rev-parse", "--short", "HEAD"])
	branch = run_git(["branch", "--show-current"])
	mapped_doctypes = sorted(set(api_mappings.values()))
	mapped_doctype_count = len(mapped_doctypes)
	erpnext_events = ", ".join(f"{doctype} ({', '.join(events)})" for doctype, events in doc_events.items()) or "-"

	category_lines = "\n".join(
		f"| {group} | {len(items)} | {summarize_names(items, limit=6)} |"
		for group, items in categories.items()
	)

	return f"""# NASECO FieldOps Executive Process Overview

Document revision: R{revision:03d}  
Generated: {updated}  
Source: `{branch or 'unknown'}` at `{commit}`  
Capability fingerprint: `{fingerprint}`

## Executive Message

NASECO FieldOps connects season production planning, outgrower registration, plot mapping, signed crop-cycle contracts, agronomy execution, inspection quality, input financing, seed-lot quality assessment, harvest settlement, and mobile synchronization in one managed Frappe/ERPNext application. The app creates a controlled operational record from approved seasonal intent through field execution and financial recovery.

The Season Production Plan is the management baseline. It defines regional crop and seed-category targets, parent seed and input demand, staffing capacity, milestones, readiness evidence, budget and exposure controls. Each resulting crop cycle links approved terms to the grower, plot, production lots, activities, inspections, inputs, advances, harvest value, and final settlement. The Season Command Centre and managerial reports compare actual execution with that baseline.

## Current Capability Snapshot

| Measure | Current value |
|---|---:|
| Total FieldOps DocTypes | {len(doctypes)} |
| Parent transaction/master DocTypes | {sum(1 for item in doctypes if not item.istable)} |
| Child table DocTypes | {sum(1 for item in doctypes if item.istable)} |
| Mobile/API mapped stores and objects | {len(api_mappings)} |
| Unique mobile/API target DocTypes | {mapped_doctype_count} |
| ERPNext finance event objects | {len(doc_events)} |

| Process area | Managed objects | Examples |
|---|---:|---|
{category_lines}

## Managed Process Architecture

```mermaid
flowchart LR
    subgraph L0["Season planning and approval"]
        P0([Define production targets])
        P1([Confirm input and resource capacity])
        P2([Approve and activate season plan])
    end
    subgraph L1["Field and master data"]
        A([Register outgrower])
        B([Map farm plot])
        C([Approve contract and pricing policy])
    end
    subgraph L2["Crop-cycle execution"]
        D([Create crop cycle])
        E([Plan stages and agronomy activities])
        F([Schedule visits and inspections])
        G([Record compliance and corrective actions])
    end
    subgraph L3["Input and finance control"]
        H([Request stage inputs])
        I([Dispatch inputs through stock])
        J([Approve cash advances])
        K([Assess seed-lot quality])
        L([Settle grower account])
    end
    subgraph L4["Management and synchronization"]
        M([Mobile bulk sync])
        N([Conflict control])
        O([Season command centre and reports])
    end

    P0 --> P1 --> P2 --> A
    A --> B --> C --> D --> E --> F
    F --> G
    E --> H --> I --> K --> L
    D --> J --> L
    D --> O
    M --> A
    M --> F
    M --> H
    N --> M
    I --> O
    J --> O
    L --> O
```

## BPMN View 1: Season Planning And Activation

```mermaid
flowchart LR
    subgraph Management["Pool: Outgrower management"]
        S0((Season planning starts))
        S1[Define crop, category, acreage, grower and yield targets]
        S2[Allocate supervisors and inspectors]
    end
    subgraph Departments["Pool: QA, stores and finance"]
        D1[Confirm inspection standards and QA capacity]
        D2[Confirm parent seed, inputs and warehouses]
        D3[Confirm budget, cash flow and exposure ceiling]
    end
    subgraph Approval["Pool: Operations approval"]
        A1{{Mandatory readiness complete?}}
        A2[Approve production plan]
        A3[Activate season command centre]
    end

    S0 --> S1 --> S2 --> D1 --> D2 --> D3 --> A1
    A1 -- No --> S1
    A1 -- Yes --> A2 --> A3
```

## BPMN View 2: Outgrower To Active Crop Cycle

```mermaid
flowchart LR
    subgraph Farmer["Pool: Outgrower"]
        F0((Start))
        F1[Provide registration and plot information]
    end
    subgraph FieldTeam["Pool: Field operations"]
        O1[Create Outgrower]
        P1[Capture Farm Plot GPS polygon]
        P2[Validate plot area, centroid, and perimeter]
        C0[Select approved contract template and pricing policy]
        C1[Sign production contract]
        C2[Create Crop Cycle and production lots]
    end
    subgraph App["Pool: FieldOps app"]
        S1{{Master data complete?}}
        S2[Set crop cycle status and next inspection context]
        S3[(Operational crop-cycle record)]
    end

    F0 --> F1 --> O1 --> P1 --> P2 --> S1
    S1 -- No --> O1
    S1 -- Yes --> C0 --> C1 --> C2 --> S2 --> S3
```

## BPMN View 3: Agronomy, Inspection, QA Review, And Corrective Action

```mermaid
flowchart LR
    subgraph Planner["Pool: Agronomy planning"]
        A1[Define crop recipe and stages]
        A2[Create stage activities]
        A3[Schedule field visit or inspection]
    end
    subgraph Mobile["Pool: Mobile field user"]
        M1[Capture visit GPS, notes, photos]
        M2[Complete inspection takes and measurements]
        M3[Submit completed evidence for QA review]
    end
    subgraph Control["Pool: FieldOps control"]
        C1{{All takes and GPS evidence acceptable?}}
        C2[Aggregate farmer and supervisor compliance]
        C3[Create corrective action]
        C4[Track completion]
        C5{{Quality Manager verifies?}}
        C6[Create traceable reinspection]
    end

    A1 --> A2 --> A3 --> M1 --> M2 --> C1
    C1 -- Yes --> M3 --> C2 --> C5
    C1 -- No --> M2
    C5 -- Yes --> C3 --> C4
    C5 -- Reinspection required --> C6 --> A3
```

## BPMN View 4: Inputs, Advances, Harvest, And Settlement

```mermaid
flowchart LR
    subgraph FieldOps["Pool: Field operations"]
        R1[Create Stage Input Request]
        R2[Request cash advance when eligible]
        R3[Confirm harvest receipt and production lot]
        R4[Record seed harvest quality assessment]
    end
    subgraph ERPNext["Pool: ERPNext stores and finance"]
        E1[Submit Stock Entry]
        E2[Submit Payment Entry]
        E3[Submit Quality Inspection]
        E4[Create assessed Purchase Invoice]
    end
    subgraph Control["Pool: FieldOps finance controls"]
        C1[Sync dispatched stock to request]
        C2[Sync cash advance to crop cycle]
        C3[Apply yield, purity, germination and penalty rules]
        C4{{Exposure within policy?}}
        C5[Recover inputs and supplier advances]
        C6[Track net payable and deferred bonus]
    end

    R1 --> E1 --> C1 --> C4
    R2 --> E2 --> C2 --> C4
    R3 --> E3 --> R4 --> C3 --> E4 --> C5 --> C6
    C4 -- Yes --> C5
    C4 -- No --> R2
```

## How The App Manages Interdependencies

| Interdependency | App control |
|---|---|
| Season plan to operations | Approved regional targets, input demand, resource allocation, milestones and readiness controls govern season activation. |
| Grower to land | Outgrower records link to Farm Plot GPS boundaries and plot photos. |
| Land to production | Farm Plot records anchor Crop Cycles, seasons, crops, varieties, and assignments. |
| Contract to crop cycle | Submitted contract templates and category-specific pricing policies are snapshotted into signed production contracts. |
| Production to field work | Crop Cycles drive stages, activities, agronomy reports, inspections, compliance and corrective actions. |
| Field work to input usage | Stage Input Requests and Dispatches connect agronomy plans to stock movement. |
| Input and cash exposure | Recoverable stock value, cash advanced, pending advance, exposure, and capacity live on the crop cycle. |
| Harvest to settlement | Production lots, receipts, Quality Inspections, moisture-normalized quantity, germination, genetic purity and penalties determine the initial payable value. |
| Quality to deferred bonus | Potential genetic-purity bonuses remain outside initial settlement until QA approval and due-date control. |
| Mobile to server | Role and assignment scoped sync keeps supervisors and Quality Inspectors within their own work while preserving offline operation. |
| ERPNext to FieldOps | {erpnext_events} events synchronize financial and stock outcomes into FieldOps controls. |

## Executive Control Points

1. Season readiness: production cannot be approved until mandatory target, quality, input, warehouse, staffing and finance controls are evidenced.
2. Segregation of duties: Outgrower Managers plan, Quality Inspectors capture mobile evidence, the existing Quality Manager verifies QA, and operations approvers authorize the season.
3. GPS-backed accountability: inspection takes require stable high-accuracy coordinates, plot-boundary validation and spacing around the five-metre standard.
4. Stage-based agronomy: activities, reports and recipe inputs are scheduled against the standard crop-cycle stages.
5. Exposure management: recoverable inputs and supplier advances remain visible against forecast and assessed harvest value through settlement.
6. Exception handling: reinspections, corrective actions, readiness gaps, overdue work, input shortages and sync conflicts create explicit follow-up through ToDos and reports.

## Auto-Refresh Model

This document is generated by `tools/update_executive_process_overview.py`. The generator reads DocType metadata, mobile/API mappings, and ERPNext event hooks, then increments the document revision only when the source capability fingerprint changes. A local pre-commit hook is included so the overview is refreshed before commits that improve the app.

To refresh manually:

```bash
python3 tools/update_executive_process_overview.py
```

To verify without rewriting:

```bash
python3 tools/update_executive_process_overview.py --check
```
"""


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--check", action="store_true", help="Fail if the generated document is stale")
	args = parser.parse_args()

	doctypes = load_doctypes()
	api_mappings = parse_api_store_mappings()
	doc_events = parse_doc_events()
	snapshot = build_snapshot(doctypes, api_mappings, doc_events)
	fingerprint = stable_fingerprint(snapshot)
	state = load_state()
	revision = int(state.get("revision") or 0)
	fingerprint_changed = state.get("fingerprint") != fingerprint
	if fingerprint_changed:
		revision += 1
	elif revision == 0:
		revision = 1
		fingerprint_changed = True
	updated_display = (
		datetime.now().strftime("%Y-%m-%d %H:%M")
		if fingerprint_changed or not DOC_PATH.exists()
		else state.get("updated_display") or datetime.now().strftime("%Y-%m-%d %H:%M")
	)

	document = render_document(doctypes, api_mappings, doc_events, revision, fingerprint, updated_display)

	if args.check:
		current = DOC_PATH.read_text() if DOC_PATH.exists() else ""
		if current != document:
			print(f"{DOC_PATH.relative_to(ROOT)} is stale. Run tools/update_executive_process_overview.py.")
			return 1
		return 0

	DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
	DOC_PATH.write_text(document)
	write_state(revision, fingerprint, updated_display)
	print(f"Updated {DOC_PATH.relative_to(ROOT)} at revision R{revision:03d}.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
