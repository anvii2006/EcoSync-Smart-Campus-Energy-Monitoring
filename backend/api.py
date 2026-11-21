"""Shared HTTP contracts for Lambda proxy integration and local HTTP."""

from datetime import timedelta
from hmac import compare_digest
import json

from energy import ApiError, timestamp, validate_room


MAX_BODY = 4096
ROUTES = {
    "/rooms": {"GET"}, "/readings": {"GET", "POST"}, "/analytics": {"GET"},
    "/alerts": {"GET"}, "/config": {"GET", "PUT"},
}


def reply(code, data, origin):
    return code, {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": origin,
        "Vary": "Origin",
        "Cache-Control": "no-store",
    }, json.dumps(data, separators=(",", ":"), allow_nan=False)


def decode_body(body):
    if len(body) > MAX_BODY:
        raise ApiError(413, "Request body exceeds 4 KiB.")
    try:
        return json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise ApiError(400, "Request body must contain valid JSON.") from None


def count(query, default, maximum):
    try:
        value = int(query.get("limit", default))
    except (TypeError, ValueError):
        raise ApiError(400, "limit must be an integer.") from None
    if not 1 <= value <= maximum:
        raise ApiError(400, f"limit must be between 1 and {maximum}.")
    return value


def handle(service, token, origin, method, path, query=None, headers=None, body=b""):
    query = query or {}
    headers = {key.lower(): value for key, value in (headers or {}).items()}
    try:
        if path not in ROUTES:
            raise ApiError(404, "Route not found.")
        if method == "OPTIONS":
            return 204, {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            }, ""
        if method not in ROUTES[path]:
            code, response_headers, payload = reply(405, {"error": "Method not allowed."}, origin)
            response_headers["Allow"] = ", ".join(sorted(ROUTES[path] | {"OPTIONS"}))
            return code, response_headers, payload
        if method in {"POST", "PUT"}:
            auth = headers.get("authorization", "")
            if not token or not compare_digest(auth.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
                code, response_headers, payload = reply(401, {"error": "A valid bearer token is required."}, origin)
                response_headers["WWW-Authenticate"] = "Bearer"
                return code, response_headers, payload
            if headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                raise ApiError(415, "Content-Type must be application/json.")
            data = decode_body(body)
            if path == "/config":
                return reply(200, service.update_config(data), origin)
            status, result = service.ingest(data)
            return reply(status, result, origin)

        room_id = validate_room(query["room_id"]) if "room_id" in query else None
        if path == "/config":
            result = service.config()
        elif path == "/rooms":
            result = service.rooms()
            result["recommendations"] = service.recommendations(result["rooms"])
        elif path == "/readings":
            validate_room(room_id)
            end = timestamp(query["to"]) if "to" in query else service.clock() + timedelta(seconds=30)
            start = timestamp(query["from"]) if "from" in query else end - timedelta(hours=24)
            if end < start or end - start > timedelta(days=31):
                raise ApiError(400, "The reading window must be ordered and span at most 31 days.")
            result = service.readings(room_id, start, end, count(query, 50, 500))
        elif path == "/alerts":
            result = service.alerts(room_id, count(query, 50, 200))
        else:
            period = query.get("period", "today")
            if period not in {"today", "7d", "30d"}:
                raise ApiError(400, "period must be today, 7d or 30d.")
            result = service.analytics(period, room_id)
        return reply(200, result, origin)
    except ApiError as error:
        return reply(error.status, {"error": str(error)}, origin)
