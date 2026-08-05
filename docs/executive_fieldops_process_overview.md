# NASECO FieldOps Executive Process Overview

Document revision: R006  
Generated: 2026-07-31 12:05  
Source: `main` at `3e047ed`  
Capability fingerprint: `6110e6ed2a74b463`

## Executive Message

NASECO FieldOps connects season production planning, outgrower registration, plot mapping, signed crop-cycle contracts, agronomy execution, inspection quality, input financing, seed-lot quality assessment, harvest settlement, and mobile synchronization in one managed Frappe/ERPNext application. The app creates a controlled operational record from approved seasonal intent through field execution and financial recovery.

The Season Production Plan is the management baseline. It defines regional crop and seed-category targets, parent seed and input demand, staffing capacity, milestones, readiness evidence, budget and exposure controls. Each resulting crop cycle links approved terms to the grower, plot, production lots, activities, inspections, inputs, advances, harvest value, and final settlement. The Season Command Centre and managerial reports compare actual execution with that baseline.

## Current Capability Snapshot

| Measure | Current value |
|---|---:|
| Total FieldOps DocTypes | 58 |
| Parent transaction/master DocTypes | 35 |
| Child table DocTypes | 23 |
| Mobile/API mapped stores and objects | 79 |
| Unique mobile/API target DocTypes | 39 |
| ERPNext finance event objects | 4 |

| Process area | Managed objects | Examples |
|---|---:|---|
| Grower and land master data | 6 | Farm Plot, Outgrower, Plot Crop Assignment, Plot Photo, Plot Vertex, Region |
| Crop planning and agronomy | 10 | Agronomy Activity Template, Crop, Crop Cycle, Crop Cycle Stage, Crop Recipe, Crop Variety, plus 4 more |
| Season planning and command control | 6 | Season Input Requirement, Season Milestone, Season Production Plan, Season Production Target, Season Readiness Item, Season Resource Allocation |
| Contract and commercial governance | 6 | Crop Production Lot, Outgrower Pricing Band, Outgrower Pricing Policy, Outgrower Production Contract, Production Contract Signatory, Production Contract Template |
| Field execution and inspection | 13 | Field Corrective Action, Field Visit, Inspection, Inspection Attribute, Inspection Parameter, Inspection Result, plus 7 more |
| Inputs, advances, harvest, and settlement | 11 | Crop Cycle Advance Request, Crop Cycle Harvest Receipt, Crop Cycle Settlement, Crop Cycle Settlement Adjustment, Crop Cycle Settlement Cash Advance, Crop Cycle Settlement Pricing Line, plus 5 more |
| Mobile sync and controls | 2 | Sync Conflict, Sync Log |
| Other app objects | 4 | Agronomy Report, Agronomy Report Parameter, Agronomy Report Result, Agronomy Report Template |

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
        A1{Mandatory readiness complete?}
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
        S1{Master data complete?}
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
        C1{All takes and GPS evidence acceptable?}
        C2[Aggregate farmer and supervisor compliance]
        C3[Create corrective action]
        C4[Track completion]
        C5{Quality Manager verifies?}
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
        C4{Exposure within policy?}
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
| ERPNext to FieldOps | Stock Entry (before_validate, before_submit, on_submit, on_cancel), Payment Entry (on_submit, on_cancel), Purchase Receipt (before_validate), Purchase Invoice (on_submit, on_cancel) events synchronize financial and stock outcomes into FieldOps controls. |

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
