# EcoSync – Smart Campus Energy Monitoring System

**A cloud-based solution for smarter energy monitoring and sustainable campus management.**

## Project Overview

EcoSync is a smart campus energy monitoring system that transforms electricity consumption data into meaningful insights. It monitors three campus environments—Computer Lab, Library, and Classroom—using simulated sensor readings.

The system provides real-time energy monitoring, consumption analytics, electricity cost estimation, carbon footprint tracking, and automatic anomaly detection.

Built on AWS serverless architecture, EcoSync demonstrates how cloud computing can make energy monitoring scalable, efficient, and accessible.

## Technologies Used

| Component | Technology |
|---|---|
| Frontend | React, Vite, JavaScript, Recharts |
| Backend | Python, AWS Lambda |
| API | Amazon API Gateway |
| Database | Amazon DynamoDB |
| Hosting | AWS Amplify |
| Monitoring | Amazon CloudWatch |
| Infrastructure | AWS SAM, CloudFormation |
| Sensor Simulation | Python |

## Cloud Architecture

**Python Simulator → API Gateway → AWS Lambda → DynamoDB → React Dashboard (AWS Amplify)**

The Python simulator generates electricity readings every five seconds. API Gateway forwards the readings to AWS Lambda for processing, energy calculations, and anomaly detection. DynamoDB stores the data, which is retrieved and displayed through the cloud-hosted React dashboard. CloudWatch monitors backend activity.

## Key Features

- **Real-Time Monitoring:** Track electricity demand across three campus rooms.
- **Energy Analytics:** Visualize consumption patterns through interactive charts.
- **Anomaly Detection:** Identify unusual power spikes and threshold violations.
- **Cost Estimation:** Calculate estimated electricity expenses.
- **Carbon Tracking:** Estimate CO₂ emissions associated with energy consumption.
- **Cloud Integration:** Use AWS serverless services for processing, storage, and hosting.

## Project Structure

```text
EcoSync/
├── backend/          # Python backend and AWS Lambda
├── frontend/         # React dashboard
├── simulator/        # Simulated sensor readings
├── tests/            # Automated tests
├── docs/             # Project documentation
├── template.yaml     # AWS infrastructure
├── amplify.yml       # Frontend deployment
└── README.md
```

## How to Run

**Requirements:** Python 3.12, Node.js 22.12+, npm.

Start the local backend:

```bash
python3.12 backend/local.py
```

Start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Start the simulator in a separate terminal from the project root:

```bash
python3.12 simulator/simulate.py
```

Open `http://127.0.0.1:5173` to view the dashboard.

## Live Deployment

**AWS-hosted Dashboard:** https://staging.d3nx4togg1oe39.amplifyapp.com

**Cloud Region:** Asia Pacific (Mumbai) – `ap-south-1`

## Conclusion

EcoSync demonstrates how cloud computing can support intelligent energy management by combining real-time monitoring, automated alerts, and sustainability analytics in a single platform.

*Note: This academic project uses simulated sensor readings rather than physical IoT devices. Cost and carbon calculations are estimates.*