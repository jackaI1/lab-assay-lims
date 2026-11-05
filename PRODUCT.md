# Product

## Platform
web

## Stack
FastAPI and SQLite are required by the brief. I chose plain HTML, CSS and JavaScript for a small local interface without a separate build server.

## Users and purpose
Jack uses this project to keep sample identities, reagent lots, plate layouts and assay calculations together and to prepare robot instructions. The workflow is register records, assign wells, import reader signals, review quality checks, and export a protocol.

## Capabilities and constraints
96-well plates, CSV/XLSX import, linear and four-parameter logistic curves, blank correction, concentrations, replicate variation, Z-prime controls, append-only audit history, and Opentrons API v2 protocol simulation. Intended for local educational use; no physical instrument validation or regulated-lab compliance is claimed.

## Design assumptions
Bench work calls for readable forms, explicit well identities and visible failure states. Bright ambient light and laptop use are assumptions chosen for the interface, not user research findings. Keyboard access and a responsive mobile layout are implementation choices.
