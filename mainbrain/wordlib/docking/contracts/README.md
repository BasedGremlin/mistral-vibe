# NEUROFORGE Docking Contracts v1.1

This folder contains machine-readable companion schemas for the contract-first docking protocol. Python dataclass contracts live in `core/contracts/spec_protocol.py`; this folder exists so Cloud and future tooling can discover protocol schemas without reverse-engineering Python code.

No runtime dependency on Pydantic is introduced in this build. The current foundation uses stdlib validation plus JSON/XML schema artifacts.
