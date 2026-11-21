"""AWS API Gateway REST proxy entry point."""

import base64
import binascii
from functools import lru_cache
import json
import logging
import os

from api import MAX_BODY, handle, reply
from dynamo_store import DynamoStore
from energy import EnergyService


logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lru_cache(maxsize=1)
def service():
    return EnergyService(DynamoStore(os.environ["TABLE_NAME"]), "aws")


def handler(event, context):
    origin = os.environ["ALLOWED_ORIGIN"]
    method, path = event.get("httpMethod", ""), event.get("resource") or event.get("path", "")
    try:
        raw = event.get("body") or ""
        if event.get("isBase64Encoded") and len(raw) <= 4 * ((MAX_BODY + 2) // 3):
            try:
                raw = base64.b64decode(raw, validate=True)
            except (ValueError, binascii.Error):
                code, headers, body = reply(400, {"error": "Invalid request encoding."}, origin)
                return {"statusCode": code, "headers": headers, "body": body}
        elif isinstance(raw, str):
            raw = raw.encode()
        code, headers, body = handle(
            service(), os.environ["WRITE_TOKEN"], origin, method, path,
            event.get("queryStringParameters"), event.get("headers"), raw,
        )
        if method == "POST" and code == 201:
            result = json.loads(body)
            logger.info("reading_processed room_id=%s alert_transition=%s",
                        result["reading"]["room_id"], result["alert_transition"])
        logger.info("api method=%s route=%s status=%s request_id=%s",
                    method, path, code, context.aws_request_id)
    except Exception:
        logger.exception("Unhandled EcoSync request failure")
        code, headers, body = reply(500, {"error": "Internal API error."}, origin)
    return {"statusCode": code, "headers": headers, "body": body}
