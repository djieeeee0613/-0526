import json
import logging
import os
import re
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CALLSIGN_RE = re.compile(r"^[a-zA-Z0-9_]{1,20}$")
TABLE_NAME = os.environ["TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def _broadcast(domain_name, stage, payload, exclude_id=None):
    endpoint_url = f"https://{domain_name}/{stage}"
    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)
    data = json.dumps(payload).encode("utf-8")

    connections = []
    scan_kwargs = {"ProjectionExpression": "connectionId"}
    while True:
        response = table.scan(**scan_kwargs)
        connections.extend(response["Items"])
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    for conn in connections:
        conn_id = conn["connectionId"]
        if conn_id == exclude_id:
            continue
        try:
            apigw.post_to_connection(ConnectionId=conn_id, Data=data)
        except apigw.exceptions.GoneException:
            table.delete_item(Key={"connectionId": conn_id})
        except Exception as e:
            logger.error("Failed to send to %s: %s", conn_id, e)


def handler(event, context):
    try:
        rc = event["requestContext"]
        connection_id = rc["connectionId"]
        domain_name = rc.get("domainName", "")
        stage = rc.get("stage", "")

        qs = event.get("queryStringParameters") or {}
        callsign = (qs.get("callsign") or "").strip()

        if not CALLSIGN_RE.match(callsign):
            return {"statusCode": 400, "body": "Invalid or missing callsign"}

        connected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        table.put_item(Item={
            "connectionId": connection_id,
            "callsign": callsign,
            "connectedAt": connected_at,
        })

        try:
            _broadcast(domain_name, stage, {
                "type": "system",
                "event": "user_joined",
                "callsign": callsign,
                "timestamp": connected_at,
            }, exclude_id=connection_id)
        except Exception as e:
            logger.error("Broadcast user_joined failed: %s", e)

        return {"statusCode": 200, "body": "Connected"}

    except Exception as e:
        logger.error("Connect error: %s", e, exc_info=True)
        return {"statusCode": 500, "body": "Internal server error"}
