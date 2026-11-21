"""DynamoDB queries and atomic writes. No AWS dependencies in local mode."""

from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from store import Conflict, Put


def to_dynamo(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: to_dynamo(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dynamo(item) for item in value]
    return value


def from_dynamo(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: from_dynamo(item) for key, item in value.items()}
    if isinstance(value, list):
        return [from_dynamo(item) for item in value]
    return value


class DynamoStore:
    def __init__(self, table, client=None):
        self.table = table
        self.client = client if client is not None else boto3.client("dynamodb")
        self.serializer = TypeSerializer()
        self.deserializer = TypeDeserializer()

    def encode(self, value):
        return {key: self.serializer.serialize(to_dynamo(item)) for key, item in value.items()}

    def decode(self, item):
        return {key: from_dynamo(self.deserializer.deserialize(value))
                for key, value in item.items() if key not in ("pk", "sk")}

    def get(self, pk, sk):
        result = self.client.get_item(
            TableName=self.table, Key=self.encode({"pk": pk, "sk": sk}), ConsistentRead=True,
        )
        return self.decode(result["Item"]) if "Item" in result else None

    def query(self, pk, lower, upper, limit=None, newest=False):
        params = {
            "TableName": self.table,
            "KeyConditionExpression": "pk = :pk AND sk BETWEEN :lower AND :upper",
            "ExpressionAttributeValues": self.encode({":pk": pk, ":lower": lower, ":upper": upper}),
            "ConsistentRead": True,
            "ScanIndexForward": not newest,
        }
        items = []
        while True:
            if limit is not None:
                params["Limit"] = limit - len(items)
            result = self.client.query(**params)
            items.extend((item["sk"]["S"], self.decode(item)) for item in result["Items"])
            if not result.get("LastEvaluatedKey") or (limit is not None and len(items) >= limit):
                return items
            params["ExclusiveStartKey"] = result["LastEvaluatedKey"]

    def commit(self, changes):
        transactions = []
        for change in changes:
            key = {"pk": change.pk, "sk": change.sk}
            if isinstance(change, Put):
                put = {"TableName": self.table, "Item": self.encode({**change.value, **key})}
                if change.guard is not None:
                    field, expected = change.guard
                    put["ExpressionAttributeNames"] = {"#guard": field}
                    if expected is None:
                        put["ConditionExpression"] = "attribute_not_exists(#guard)"
                    else:
                        put["ConditionExpression"] = "#guard = :expected"
                        put["ExpressionAttributeValues"] = self.encode({":expected": expected})
                transactions.append({"Put": put})
            else:
                fields = list(change.fields)
                names = {f"#f{i}": field for i, field in enumerate(fields)}
                values = {f":v{i}": change.fields[field] for i, field in enumerate(fields)}
                transactions.append({"Update": {
                    "TableName": self.table, "Key": self.encode(key),
                    "UpdateExpression": "ADD " + ", ".join(f"#f{i} :v{i}" for i in range(len(fields))),
                    "ExpressionAttributeNames": names,
                    "ExpressionAttributeValues": self.encode(values),
                }})
        try:
            self.client.transact_write_items(TransactItems=transactions)
        except ClientError as error:
            code = error.response["Error"]["Code"]
            reasons = {reason.get("Code") for reason in error.response.get("CancellationReasons", [])}
            if code == "TransactionConflictException" or (
                code == "TransactionCanceledException"
                and reasons.intersection({"ConditionalCheckFailed", "TransactionConflict"})
            ):
                raise Conflict from error
            if code in {"ThrottlingException", "ThrottlingError", "ProvisionedThroughputExceededException",
                        "RequestLimitExceeded", "InternalServerError", "TransactionInProgressException"} or (
                code == "TransactionCanceledException"
                and reasons.intersection({"ProvisionedThroughputExceeded", "ThrottlingError"})
            ):
                from energy import ApiError
                raise ApiError(503, "Storage is temporarily unavailable. Retry shortly.") from error
            raise
