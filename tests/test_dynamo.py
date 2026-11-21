import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    import boto3
    from moto import mock_aws
except ImportError:
    boto3 = None

from energy import iso


@unittest.skipUnless(boto3, "Install tests/requirements.txt for the emulated DynamoDB test.")
class DynamoIntegrationTest(unittest.TestCase):
    def test_lambda_routes_and_atomic_dynamo_rollups(self):
        from lambda_app import handler, service

        with mock_aws(), patch.dict(os.environ, {
            "AWS_DEFAULT_REGION": "ap-south-1",
            "TABLE_NAME": "EcoSyncTest",
            "WRITE_TOKEN": "test-token-from-local-emulator",
            "ALLOWED_ORIGIN": "https://dashboard.example.org",
        }):
            service.cache_clear()
            self.addCleanup(service.cache_clear)
            client = boto3.client("dynamodb")
            client.create_table(
                TableName=os.environ["TABLE_NAME"], BillingMode="PAY_PER_REQUEST",
                KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
                AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            )

            def send(method, path, payload=None, query=None):
                event = {
                    "httpMethod": method, "resource": path,
                    "headers": {"Authorization": "Bearer " + os.environ["WRITE_TOKEN"], "Content-Type": "application/json"},
                    "queryStringParameters": query, "body": json.dumps(payload) if payload else None,
                }
                response = handler(event, SimpleNamespace(aws_request_id="test"))
                self.assertEqual(response["headers"]["Access-Control-Allow-Origin"], os.environ["ALLOWED_ORIGIN"])
                return response["statusCode"], json.loads(response["body"])

            start = datetime(2026, 7, 3, 9, 0, tzinfo=timezone.utc)
            service().clock = lambda: start + timedelta(seconds=16)
            powers = (2, 6, 6.5, 2)
            for i, power in enumerate(powers):
                payload = {"room_id": "computer-lab", "power_kw": power, "timestamp": iso(start + timedelta(seconds=i * 5))}
                self.assertEqual(send("POST", "/readings", payload)[0], 201)
            self.assertEqual(send("POST", "/readings", payload)[0], 200)
            rooms = send("GET", "/rooms")[1]
            self.assertEqual(rooms["current_power_kw"], 2)
            analytics = send("GET", "/analytics")[1]
            self.assertAlmostEqual(analytics["totals"]["energy_kwh"], 72.5 / 3600)
            alerts = send("GET", "/alerts")[1]
            self.assertEqual(alerts["active"], [])
            self.assertEqual(len(alerts["history"]), 1)
            self.assertEqual(alerts["history"][0]["peak_kw"], 6.5)
            recent = send("GET", "/readings", query={"room_id": "computer-lab", "limit": "2"})
            self.assertEqual([item["power_kw"] for item in recent[1]["readings"]], [2, 6.5])
            self.assertEqual(send("GET", "/config")[1]["mode"], "aws")
            self.assertEqual(send("PUT", "/config", {"tariff_inr_per_kwh": 9.5})[1]["tariff_inr_per_kwh"], 9.5)
            item = client.get_item(TableName=os.environ["TABLE_NAME"],
                                   Key={"pk": {"S": "ROOM#computer-lab"}, "sk": {"S": "DAY#2026-07-03"}})
            self.assertIn("energy_nkwh", item["Item"])
