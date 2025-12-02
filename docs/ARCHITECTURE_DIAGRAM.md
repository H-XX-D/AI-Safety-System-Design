# System Architecture Diagram

```mermaid
graph LR
    classDef implemented fill:#d3f9d8,stroke:#2f855a,color:#1a202c,font-size:14px;
    classDef partial fill:#fff4c2,stroke:#b7791f,color:#1a202c,font-size:14px;
    classDef planned fill:#fed7d7,stroke:#c53030,color:#1a202c,font-size:14px;

    subgraph Research Cluster
        A1[Research AI 1]
        A2[Research AI 2]
        A3[Research AI 3]
        A4[Research AI 4]
        A5[Research AI 5]
    end

    ORC[ORCA Orchestrator]
    VAL[Air-Gapped Validator]
    WORM[WORM USB (Immutable Core Values)]
    HT[Hardware Translators x3]
    HUMAN[(Human Operators)]

    subgraph Monitoring
        MEM[Memory Merkle Auditor]
        REP[Reputation System]
    end

    subgraph Legend
        LEG_IMPL[Implemented]:::implemented
        LEG_PART[Partially Implemented]:::partial
        LEG_PLAN[Planned / Stub]:::planned
    end

    A1 --> ORC
    A2 --> ORC
    A3 --> ORC
    A4 --> ORC
    A5 --> ORC

    ORC -->|Proposals / Reviews| VAL
    VAL -->|Verdicts / Penalties| ORC

    ORC -->|Approved Updates| WORM
    WORM -->|Core Values Hash| HT

    ORC -->|Protocol Messages| HT
    HT -->|Human-Readable Output| HUMAN

    HUMAN -->|Approval / Oversight| VAL

    HT -->|Consensus Signatures| ORC

    ORC --> MEM
    ORC --> REP
    MEM --> ORC
    REP --> ORC

    class A1,A2,A3,A4,A5,VAL,HT planned;
    class ORC partial;
    class WORM,REP,MEM implemented;
    class HUMAN implemented;
```

## Notes
- **Implemented**: Memory Merkle auditor, reputation engine, and software WORM guard are shipping components with passing tests.
- **Partially Implemented**: The orchestrator handles proposal intake, debate, sandbox plumbing, and reporting, but still relies on host fallbacks for Windows and lacks attestations for sandbox artifacts.
- **Planned / Stubbed**: Research agents, hardware translators, and the air-gapped validator remain specifications or software shims until hardware is built.
- Hardware Translators will eventually host deterministic mapping + consensus voting on air-gapped devices.
- WORM USB should enforce immutability of core values / protocol manifests once physical media replaces the JSON simulation.
- Air-Gapped Validator is intended to execute high-assurance verification & penalty logic outside the orchestrator trust boundary.
