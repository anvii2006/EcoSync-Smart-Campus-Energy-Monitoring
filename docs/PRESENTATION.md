# EcoSync presentation outline

| Time | Topic | What to show |
| --- | --- | --- |
| 0:00–0:45 | Problem and scope | Place the Computer Lab, Library and Classroom in the context of campus energy monitoring. Show the overview. |
| 0:45–1:45 | AWS architecture | Trace a write from the simulator through API Gateway and Lambda to DynamoDB. Trace the read path from the Amplify dashboard and show CloudWatch. |
| 1:45–2:30 | Calculations and detection | Explain average power × elapsed hours, tariffs and the carbon factor. Describe threshold and spike rules, and one alert per continuous event. |
| 2:30–4:15 | Live ingestion | Start the simulator. Show the Lambda request log, a DynamoDB reading item, the current power card, and chart updates. |
| 4:15–5:15 | Anomaly and recovery | Type `computer-lab` in the simulator. Show the 6.4 kW spike, active alert, recommendation, and resolution. |
| 5:15–6:15 | Analytics and impact | Change the analytics time range, compare rooms, and explain the change in estimated cost and CO₂. |
| 6:15–7:00 | Verification and close | Summarize automated tests, local browser results, and the cloud verification performed during the demo. Cover the stack cleanup command. |

For a local rehearsal, seed a fresh SQLite database with `python3.12 simulator/seed_local.py` and use the [local setup](../README.md#run-locally). For the cloud demonstration, follow the [AWS steps](../README.md#deploy-to-aws) after approval and show the deployed app’s **AWS cloud mode** label.
