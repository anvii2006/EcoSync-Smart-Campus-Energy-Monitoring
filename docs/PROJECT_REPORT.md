# EcoSync
## Cloud-Based Smart Energy Consumption and Carbon Footprint Dashboard

### Problem statement

Room-level electricity demand varies throughout the day. Without recent readings or history, campus operators have limited visibility into unexpected loads, accumulated costs and electricity-related emissions.

### Objectives

- Collect simulated electricity readings for three campus rooms every five seconds.
- Detect abnormal consumption and preserve each event through recovery.
- Show room comparisons, historical usage, estimated bills and estimated CO₂ emissions.
- Use managed AWS services for ingestion, processing, storage, hosting and observability.

### System architecture and cloud services

A Python simulator sends HTTPS requests to Amazon API Gateway. A Python 3.12 Lambda validates and processes the data, then persists readings, rollups, settings and alerts in DynamoDB. A React dashboard hosted by Amplify polls API Gateway for updates. CloudWatch receives Lambda logs and service metrics. AWS SAM defines the REST API, Lambda, data table, log retention and scoped IAM permissions. [Architecture diagram](ARCHITECTURE.md)

### Implementation

Each accepted interval contributes the mean of its two power readings multiplied by elapsed hours. Energy is allocated to half-hour and daily rollups. The example cost and carbon factors are ₹8/kWh and 0.71 kg CO₂/kWh. The dashboard labels both results as estimates and identifies its data source.

An alert opens when power exceeds the room limit or jumps sharply from its recent baseline. A continuous event updates one alert until a normal reading records recovery. The system recommends investigating high loads and switching off idle equipment after hours. A guarded transaction keeps the room state, reading, alert and aggregates consistent. The browser receives public demo data through GET routes. A bearer token is required for ingestion and settings changes.

### Testing and results

All 19 automated tests passed on Python 3.12. Tests covered interval calculations, day boundaries, cost and emissions, recommendations, alert lifecycle, duplicate ingestion, SQLite persistence, request validation, and a Lambda-to-DynamoDB integration test using an emulator. The frontend production build passed, along with SAM template validation and a local SAM build. In browser testing, new stored readings appeared automatically and the chart showed gaps when telemetry stopped. A simulator test opened and resolved one alert per room and confirmed that all 36 readings and derived records survived a backend restart. Live deployment remains subject to authorization and AWS verification.

### Conclusion

EcoSync provides room-level telemetry, anomaly history and reproducible estimates with a small, managed cloud architecture. The local SQLite mode supports a complete demonstration of application behavior before AWS deployment.
