import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def handler(event, context):
    try:
        rc = event["requestContext"]
        connection_id = rc["connectionId"]
        domain_name = rc["domainName"]
        stage = rc["stage"]

        # Parse and validate body
        try:
            body = json.loads(event.get("body") or "")
        except (json.JSONDecodeError, TypeError):
            return {"statusCode": 400, "body": "Missing or invalid text"}

        text = body.get("text")
        if not text or not isinstance(text, str):
            return {"statusCode": 400, "body": "Missing or invalid text"}
        text = text.strip()
        if not text or len(text) > 1000:
            return {"statusCode": 400, "body": "Missing or invalid text"}

        # Resolve callsign from DynamoDB (prevents spoofing)
        response = table.get_item(Key={"connectionId": connection_id})
        sender = response.get("Item")
        if not sender:
            return {"statusCode": 400, "body": "Unknown sender"}
        callsign = sender["callsign"]

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            "type": "message",
            "callsign": callsign,
            "text": text,
            "timestamp": timestamp,
        }

        # Paginated scan for all active connections
        connections = []
        scan_kwargs = {"ProjectionExpression": "connectionId"}
        while True:
            resp = table.scan(**scan_kwargs)
            connections.extend(resp["Items"])
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

        endpoint_url = f"https://{domain_name}/{stage}"
        apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)
        data = json.dumps(payload).encode("utf-8")

        for conn in connections:
            conn_id = conn["connectionId"]
            try:
                apigw.post_to_connection(ConnectionId=conn_id, Data=data)
            except apigw.exceptions.GoneException:
                table.delete_item(Key={"connectionId": conn_id})
            except Exception as e:
                logger.error("Failed to send to %s: %s", conn_id, e)

        return {"statusCode": 200, "body": "Message sent"}

    except Exception as e:
        logger.error("SendMessage error: %s", e, exc_info=True)
        return {"statusCode": 500, "body": "Internal server error"}
