# EcoSync

EcoSync is a campus electricity monitoring dashboard for the Computer Lab, Library, and Classroom. It refreshes every five seconds, tracks anomalous loads, and estimates energy charges and carbon emissions from simulated sensor readings.

| Layer | Technology |
| --- | --- |
| Dashboard | React, Vite, Tailwind CSS, Recharts, Lucide React |
| Sensor simulator | Python 3.12 and HTTP |
| Cloud backend | API Gateway REST API, Python 3.12 Lambda, DynamoDB, CloudWatch |
| Deployment | AWS SAM and Amplify Hosting |
| Local backend | Python 3.12 HTTP server and persistent SQLite |

[Architecture and data model](docs/ARCHITECTURE.md) · [Project report](docs/PROJECT_REPORT.md) · [Presentation outline](docs/PRESENTATION.md)

## Run locally

Install Python 3.12 and Node.js 22.12 or later with npm. From the project root, run these commands in separate terminals.

**Terminal 1 — API**

```sh
python3.12 backend/local.py
```

**Terminal 2 — dashboard**

```sh
cd frontend
npm ci
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). From an empty database, the dashboard shows an empty chart until the API saves the first reading. **Recent** on Overview and Room Monitoring plots up to 60 stored power readings for the selected room from the past 24 hours. It refreshes automatically every five seconds. **Today**, **7 days**, and **30 days** use the saved analytics rollups.

**Terminal 3 — simulator**

```sh
python3.12 simulator/simulate.py
```

Type `computer-lab`, `library`, or `classroom` into the simulator terminal and press Enter to trigger a two-reading spike. For an unattended four-cycle demo, use `python3.12 simulator/simulate.py --spike computer-lab --cycles 4` as the sole simulator process. The event should open on cycle two, continue on cycle three, and resolve on cycle four. A room becomes stale after 20 seconds without a reading. Its last value remains in history and is excluded from current campus power.

Restart the API with the same database path to keep readings, alerts, and settings. The default database is `ecosync.sqlite3` at the project root.

To fill the local charts with seven calendar days of simulated history, run `python3.12 simulator/seed_local.py` **before starting the API and simulator**, using a fresh database. The seed also includes a resolved Computer Lab alert from the previous day. To keep a separate demo database, pass the same `--db demo.sqlite3` to both `seed_local.py` and `backend/local.py`.

The default local token is `ecosync-local-demo`. To replace it, set `ECOSYNC_TOKEN` in both the API and simulator terminals. The backend binds to loopback. If you change the frontend origin, set `ECOSYNC_ALLOWED_ORIGIN` on the local API. Set `VITE_API_BASE_URL` in the frontend environment or copy `frontend/.env.example` to `frontend/.env.local` to change the API base URL. Production builds require an explicit API URL. Connection errors are visible and the UI labels cached results when a refresh fails.

## REST API

Routes below are relative to `http://127.0.0.1:8000` locally and to the stack’s `ApiUrl` in AWS. Write requests require `Authorization: Bearer <token>` and `Content-Type: application/json`.

| Method and path | Query/body | Response |
| --- | --- | --- |
| `POST /readings` | JSON payload shown below | `201` accepted with alert transition, or `200` for an identical retry |
| `GET /readings` | Required `room_id`. Optional ISO datetime `from` and `to` (inclusive), `limit` 1–500 | Newest first. Defaults to 50 readings from the past 24 hours. Maximum time range is 31 days. |
| `GET /rooms` | — | Room IDs, names, thresholds, latest readings, freshness, active alerts, current campus power, reporting-room count, and recommendations |
| `GET /analytics` | `period=today\|7d\|30d`, optional `room_id` | Totals, daily and room series, per-room data availability, and the tariff and emissions factor applied to the results. Today uses 30-minute average power, and longer ranges use daily energy. |
| `GET /alerts` | Optional `room_id`, `limit` 1–200 (default 50) | Active alerts plus most recent history |
| `GET /config` | — | Tariff, emission factor, thresholds, timezone, operating hours, API mode and sampling settings |
| `PUT /config` | Any subset of `tariff_inr_per_kwh`, `emission_kg_per_kwh`, `thresholds_kw` | Updated settings. Threshold keys can be updated individually. |

```json
{
  "room_id": "computer-lab",
  "timestamp": "2026-07-03T09:00:00.000Z",
  "power_kw": 2.15
}
```

Use a current timestamp when testing a live session. Room IDs are `computer-lab`, `library`, and `classroom`. Power must be 0–100 kW. Timestamps require an offset and are stored as UTC with millisecond precision. Timestamps before 2000 and writes beyond 30 seconds in the future return `400`. Out-of-order writes and conflicting readings at an existing timestamp return `409`. Other responses include `401` for missing or invalid authentication, `413` for oversized bodies, `415` for unsupported content types, and `503` for retryable backend contention. Errors have a JSON `error` message.

Update local configuration using the following example. For AWS, use the stack API URL and supply the private token through your terminal environment.

```sh
curl --fail-with-body -X PUT http://127.0.0.1:8000/config \
  -H 'Authorization: Bearer ecosync-local-demo' \
  -H 'Content-Type: application/json' \
  -d '{"tariff_inr_per_kwh":8,"emission_kg_per_kwh":0.71,"thresholds_kw":{"computer-lab":4.8}}'
```

### Calculations and alerts

- Each pair of consecutive readings defines a trapezoid. Energy is the mean of endpoint powers in kW multiplied by elapsed hours. Intervals are split at reporting boundaries in Asia/Kolkata. Gaps longer than 120 seconds are skipped.
- Estimated bill is recorded energy × current tariff. The initial **₹8/kWh** models only the energy charge. Estimated carbon is recorded energy × the current emission factor. The initial **0.71 kg CO₂/kWh** is an illustrative grid intensity for the semester demo. Configure it for the electricity mix you intend to model. Applying new factors recalculates estimates for historical periods on read.
- A reading above its room threshold opens an alert, as does a rise of at least 0.75 kW and at least 1.8× the recent previous reading. A spike alert remains open until power returns within 0.4 kW of its baseline, subject to the current room threshold. One alert tracks the reasons and peak for each continuous anomaly. The next normal reading records recovery.
- Rules recommend checking unexpected or high-draw equipment and switching off unused equipment when a fresh reading shows elevated demand outside 08:00–18:00 IST.

## Deploy to AWS

These steps create billable AWS resources. Run them only after you have approved deployment. Use AWS CLI v2, SAM CLI, Python 3.12 and Node.js 22.12+. Configure an AWS profile with rights to manage the project’s CloudFormation, Amplify, API Gateway, Lambda, DynamoDB, CloudWatch Logs, IAM and SAM artifact bucket resources. Use an AWS profile or SSO session and keep the write token out of frontend environment variables and source.

### 1. Create an Amplify Hosting app and branch

Run the deployment commands in the same Bash or Zsh terminal from the project root. Use one AWS profile and region throughout. The CLI creates a manually hosted static web app and allocates its HTTPS origin before you configure CORS. [Amplify manual deployments](https://docs.aws.amazon.com/amplify/latest/userguide/manual-deploys.html)

```sh
export AWS_DEFAULT_REGION=ap-south-1
aws sts get-caller-identity

AMPLIFY_ID=$(aws amplify create-app --name EcoSync --platform WEB --query app.appId --output text)
aws amplify create-branch --app-id "$AMPLIFY_ID" --branch-name main --stage PRODUCTION
AMPLIFY_DOMAIN=$(aws amplify get-app --app-id "$AMPLIFY_ID" --query app.defaultDomain --output text)
AMPLIFY_ORIGIN="https://main.$AMPLIFY_DOMAIN"
printf '%s\n' "$AMPLIFY_ORIGIN"
```

Keep the Amplify app ID for cleanup.

### 2. Deploy the backend with SAM

Generate a private token in a private terminal with `openssl rand -hex 32`. Keep it for both the SAM prompt and the simulator. Check the packaged template and review the CloudFormation change set. [SAM deploy reference](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html)

```sh
sam validate --lint --region "$AWS_DEFAULT_REGION"
sam build
sam deploy --guided --stack-name ecosync-demo --region "$AWS_DEFAULT_REGION" --capabilities CAPABILITY_IAM
```

- Enter the exact `AMPLIFY_ORIGIN` printed above as `FrontendOrigin`, with no trailing slash. Enter the generated token in the hidden `WriteToken` prompt.
- Confirm changes before deployment and allow SAM to create the template’s IAM role. If SAM asks about API Gateway authentication, the GET routes intentionally allow access to simulated data. Lambda checks the private bearer token for each write.
- Choose **No** when asked to save the arguments to a SAM configuration file. Record the managed artifact bucket name shown by SAM for cleanup.
- The write token is available to authorized Lambda configuration readers. Restrict access to Lambda configuration and rotate the token by updating the stack if necessary.

```sh
ECOSYNC_API_URL=$(aws cloudformation describe-stacks --stack-name ecosync-demo \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue | [0]" --output text)
export ECOSYNC_API_URL
curl --fail-with-body -H "Origin: $AMPLIFY_ORIGIN" -i "$ECOSYNC_API_URL/config"
```

Expect `mode: "aws"` in the JSON body and the Amplify origin in `Access-Control-Allow-Origin`.

### 3. Build and upload the dashboard

Create a ZIP containing the files inside `dist`. The only frontend setting is the public API URL. Hash-based navigation works on a static Amplify site with the default routing configuration.

```sh
(
  cd frontend
  npm ci
  VITE_API_BASE_URL="$ECOSYNC_API_URL" npm run build
  cd dist
  zip -q -r ../ecosync-dashboard.zip .
)
DEPLOYMENT=$(aws amplify create-deployment --app-id "$AMPLIFY_ID" --branch-name main --output json)
JOB_ID=$(printf '%s' "$DEPLOYMENT" | python3.12 -c 'import json,sys; print(json.load(sys.stdin)["jobId"])')
UPLOAD_URL=$(printf '%s' "$DEPLOYMENT" | python3.12 -c 'import json,sys; print(json.load(sys.stdin)["zipUploadUrl"])')
curl --fail-with-body --upload-file frontend/ecosync-dashboard.zip "$UPLOAD_URL"
unset DEPLOYMENT UPLOAD_URL
aws amplify start-deployment --app-id "$AMPLIFY_ID" --branch-name main --job-id "$JOB_ID"
aws amplify get-job --app-id "$AMPLIFY_ID" --branch-name main --job-id "$JOB_ID" --query job.summary.status
```

Open `AMPLIFY_ORIGIN` once the job status is `SUCCEED`. If you prefer connected Git builds, use a separate Amplify app connected to your repo, set the app root and `AMPLIFY_MONOREPO_APP_ROOT` to `frontend`, and set `VITE_API_BASE_URL` to the stack URL. Redeploy the backend if you switch the frontend origin. The root `amplify.yml` defines that build. [Amplify monorepo guide](https://docs.aws.amazon.com/amplify/latest/userguide/monorepo-configuration.html)

### 4. Live demonstration

1. Open the hosted dashboard and show **AWS cloud mode** and the room list.
2. From the project root, load the token without terminal echo and start the simulator against `ECOSYNC_API_URL`.

   ```sh
   printf 'EcoSync write token: '
   read -rs ECOSYNC_TOKEN
   printf '\n'
   export ECOSYNC_TOKEN
   python3.12 simulator/simulate.py
   ```

3. Open the stack’s `LogGroup` output in CloudWatch Logs. Show the `reading_processed` records from Lambda. Lambda’s `Invocations`, `Errors`, and `Duration` metrics track executions. API Gateway’s `5XXError` and the Lambda application logs surface handled HTTP failures. 
4. In DynamoDB, select the table from the `TableName` output and query `pk = ROOM#computer-lab`. Show `READING#…`, `META`, and the rollup items. Refresh the dashboard or wait five seconds to see incoming data.
5. Type `computer-lab` into the simulator and press Enter. Show `opened` then `continued` in the terminal or logs, and the active threshold/spike alert in the dashboard. After the next normal reading, show the same alert resolved and inspect the `ALERT#…` item.
6. Return to Overview and show the changing energy, bill and emissions. In Energy Analytics, switch to a seven-day chart to demonstrate daily history. A new deployment only has data for days it has collected readings.

### 5. Remove the demo resources

Stop the simulator, then delete the Amplify app and the project SAM stack. Substitute the recorded SAM artifact bucket name where indicated. These commands permanently remove the demo data and hosting.

```sh
aws amplify delete-app --app-id "$AMPLIFY_ID"
sam delete --stack-name ecosync-demo --region "$AWS_DEFAULT_REGION" \
  --s3-bucket "<recorded SAM artifact bucket>" --s3-prefix ecosync-demo
unset ECOSYNC_TOKEN
```

Check that the API, Lambda, DynamoDB table, IAM role, and project log group disappear with the stack. Confirm EcoSync’s deployment prefix is removed from the SAM bucket. If SAM created the shared `aws-sam-cli-managed-default` bootstrap stack solely for this demo, empty its artifact bucket, including object versions and delete markers, and delete that bootstrap stack in CloudFormation. Leave a pre-existing shared bootstrap stack available for other projects. Use the simulator only during the demo, close the dashboard when finished, and delete the stack to stop usage and storage charges. [SAM deletion reference](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-delete.html)

## Verification

Run the backend suite with Python 3.12. The optional test dependencies add the DynamoDB emulator and infrastructure linting. The application’s local API and simulator use the Python standard library.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r tests/requirements.txt
PYTHONPATH=backend:simulator python -m unittest discover -s tests -v
cfn-lint template.yaml --regions ap-south-1
(cd frontend && npm ci && VITE_API_BASE_URL=http://127.0.0.1:8000 npm run build)
```

The 19 automated tests cover calculations, interval splitting, zero versus missing data, all recommendation types, anomaly lifecycle, duplicate writes, input validation, configuration, SQLite persistence, the local HTTP API, simulator payloads, and the Lambda/DynamoDB adapters through emulation. The SAM template validated and built locally. The compiled dashboard was tested in the browser across all five sections, including automatic chart updates and alert filters. A separate simulator and HTTP test verified spike recovery for all three rooms and checked that all 36 readings, rollups, alerts, and settings survived a backend restart. Live AWS deployment and service verification require the steps above.
