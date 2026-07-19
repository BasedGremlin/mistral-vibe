# NEUROFORGE Docking Protocol Engine v1.1

- `validator.py` parses and validates SpecDocument / ImplementationReport contracts.
- `lifecycle.py` defines the formal state machine and guarded transitions.
- `registry.py` validates the SpecRegistry contract.
- `auditor.py` audits protocol layout and required files.

All status and validation functions are read-only.
