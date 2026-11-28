# ⚡ EcoSync – Smart Campus Energy Monitoring & Carbon Footprint Dashboard

**Real-Time Energy Intelligence | AWS Serverless Architecture | Sustainable Campus Management**

**Live Application:** [Explore EcoSync Dashboard](https://staging.d3nx4togg1oe39.amplifyapp.com)

## Project Overview

EcoSync is a cloud-native energy monitoring platform designed to improve electricity management and environmental sustainability across campus environments. It transforms simulated smart meter readings into real-time energy insights, consumption trends, estimated electricity expenses and carbon footprint analytics.

The system monitors three campus locations—Computer Lab, Library and Classroom—and automatically identifies abnormal electricity consumption through rule-based anomaly detection.

EcoSync integrates AWS serverless services for data processing, persistent storage, application hosting and operational monitoring, demonstrating the practical application of cloud computing in sustainable energy management.

## Key Features

| Feature | Functionality |
|---|---|
| Live Monitoring | Real-time power readings with five-second dashboard updates |
| Energy Analytics | Daily, weekly and monthly consumption trends |
| Room Monitoring | Individual room usage and comparison |
| Anomaly Detection | Detection of sudden power spikes and threshold violations |
| Alert Management | Active alerts, peak consumption and recovery history |
| Cost Estimation | Electricity expense calculation using configurable tariffs |
| Carbon Footprint | Estimated CO₂ emissions and sustainability insights |
| Smart Recommendations | Rule-based suggestions to reduce energy wastage |

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, Vite, Tailwind CSS, Recharts, Lucide React |
| Backend | Python 3.12, AWS Lambda |
| REST API | Amazon API Gateway |
| Cloud Database | Amazon DynamoDB |
| Cloud Hosting | AWS Amplify |
| Cloud Monitoring | Amazon CloudWatch |
| Infrastructure as Code | AWS SAM, CloudFormation |
| Data Simulation | Python Smart Meter Simulator |
| Local Development | Python HTTP Server, SQLite |

## System Architecture

```text
Python Smart Meter Simulator
            ↓ HTTPS POST
    Amazon API Gateway
            ↕
        AWS Lambda ──────→ CloudWatch
            ↕
      Amazon DynamoDB

User Browser ↔ API Gateway
      ↑
AWS Amplify (React Frontend)
```

The Python simulator generates electricity readings every five seconds and sends authenticated HTTPS requests to Amazon API Gateway. AWS Lambda validates and processes incoming data, performs energy calculations and evaluates anomaly detection rules.

Amazon DynamoDB stores readings, historical analytics, alert history and configuration settings. The React dashboard hosted on AWS Amplify retrieves information through the REST API, while Amazon CloudWatch provides application logs and operational monitoring.

AWS SAM and CloudFormation enable reproducible provisioning of backend cloud infrastructure.

## Cloud Computing Concepts Implemented

- **Serverless Computing:** Backend processing through AWS Lambda without maintaining dedicated application servers.
- **Function as a Service (FaaS):** Event-driven execution of Python functions in response to API requests.
- **Managed Cloud Database:** Persistent NoSQL storage using Amazon DynamoDB.
- **Elasticity and Scalability:** Serverless processing and on-demand database capacity support changing workloads.
- **Pay-as-you-go Model:** Cloud resource charges based on usage and applicable service pricing.
- **Infrastructure as Code:** Automated infrastructure provisioning using AWS SAM and CloudFormation.
- **Cloud Security:** IAM permissions, HTTPS communication, CORS configuration and bearer-token authentication for write operations.
- **Cloud Observability:** Application logs and performance metrics through Amazon CloudWatch.

## Technical Implementation

### Energy and Sustainability Calculations

- **Energy (kWh)** = Average power (kW) × Time (hours)
- **Estimated electricity cost** = Energy consumed × Electricity tariff
- **Estimated carbon emissions** = Energy consumed × Carbon emission factor

The default electricity tariff is ₹8/kWh, and the illustrative carbon emission factor is 0.71 kg CO₂/kWh. Both parameters are configurable.

### Anomaly Detection

EcoSync combines threshold-based and spike-based detection. An alert is generated when electricity demand exceeds a configured room threshold or increases by at least 0.75 kW and 1.8 times the previous recent reading.

The system records peak power, alert duration and recovery status. Alerts are automatically resolved when consumption returns to normal according to the recovery rules.

### REST API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/readings` | GET, POST | Retrieve and submit energy readings |
| `/rooms` | GET | Room status and monitoring |
| `/analytics` | GET | Energy consumption analytics |
| `/alerts` | GET | Anomaly alerts and recovery history |
| `/config` | GET, PUT | Retrieve and update settings |

## Project Structure

```text
EcoSync/
├── backend/          # API, Lambda and processing logic
├── frontend/         # Interactive React dashboard
├── simulator/        # Smart meter simulation
├── tests/            # Automated test suite
├── docs/             # Technical documentation
├── template.yaml     # AWS infrastructure definition
├── amplify.yml       # Cloud hosting configuration
└── README.md
```

## Live Cloud Deployment

EcoSync is deployed on Amazon Web Services, allowing users to access the dashboard without running the frontend or backend locally.

| Deployment Details | Configuration |
|---|---|
| Cloud Provider | Amazon Web Services (AWS) |
| Region | Asia Pacific (Mumbai) |
| Region Code | ap-south-1 |
| Deployment Model | Serverless Cloud Architecture |
| Frontend Hosting | AWS Amplify |
| Backend Processing | AWS Lambda |
| Database | Amazon DynamoDB |

**Live Dashboard:** https://staging.d3nx4togg1oe39.amplifyapp.com

## Running the Cloud Demonstration

**Prerequisite:** Python 3.12 and the authorized private write token.

1. Open the deployed EcoSync dashboard.
2. Configure the private `ECOSYNC_TOKEN` environment variable.
3. Run the sensor simulator from the project root:

```bash
python3.12 simulator/simulate.py --url https://47n7bkc7x0.execute-api.ap-south-1.amazonaws.com/v1
```

4. Observe live electricity readings, energy analytics, estimated costs and carbon emissions.
5. Enter `computer-lab` in the simulator terminal to trigger a temporary power spike and demonstrate anomaly detection.
6. Stop the simulator using `Ctrl + C`.

The frontend, backend, API and database operate through AWS cloud services. Only the sensor simulator runs locally. Historical readings remain accessible even after the simulator stops.

Private authentication tokens must never be committed to GitHub.

## Testing and Results

The project documentation records 19 automated tests covering energy calculations, input validation, anomaly detection, database persistence, simulator functionality and backend integration.

During the AWS cloud demonstration, EcoSync successfully detected a 6.4 kW power spike in the Computer Lab and recorded its recovery after 10 seconds, demonstrating the working anomaly detection and cloud data processing functionality.

## Future Enhancements

- Integration with physical smart meters using AWS IoT Core.
- Machine learning-based energy consumption forecasting.
- Automated email and mobile alert notifications.
- Expansion to multiple campus buildings.

## Conclusion

EcoSync demonstrates how cloud computing can support intelligent energy management and environmental sustainability. By combining serverless computation, managed cloud storage, real-time analytics and automated anomaly detection, the project provides a practical foundation for smarter campus energy management.

*Developed as an academic Cloud Computing semester project. Energy readings are simulated, while electricity costs and carbon emissions are estimated values.*
