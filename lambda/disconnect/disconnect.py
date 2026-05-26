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
        domain_name = rc.get("domainName", "")
        stage = rc.get("stage", "")

        # Fetch callsign before deletion (needed for the leave broadcast)
        response = table.get_item(Key={"connectionId": connection_id})
        callsign = response.get("Item", {}).get("callsign", "unknown")

        table.delete_item(Key={"connectionId": connection_id})

        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            payload = {
                "type": "system",
                "event": "user_left",
                "callsign": callsign,
                "timestamp": timestamp,
            }

            endpoint_url = f"https://{domain_name}/{stage}"
            apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)
            data = json.dumps(payload).encode("utf-8")

            connections = []
            scan_kwargs = {"ProjectionExpression": "connectionId"}
            while True:
                resp = table.scan(**scan_kwargs)
                connections.extend(resp["Items"])
                if "LastEvaluatedKey" not in resp:
                    break
                scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

            for conn in connections:
                conn_id = conn["connectionId"]
                try:
                    apigw.post_to_connection(ConnectionId=conn_id, Data=data)
                except apigw.exceptions.GoneException:
                    table.delete_item(Key={"connectionId": conn_id})
                except Exception as e:
                    logger.error("Failed to send to %s: %s", conn_id, e)

        except Exception as e:
            logger.error("Broadcast user_left failed: %s", e)

        return {"statusCode": 200, "body": "Disconnected"}

    except Exception as e:
        logger.error("Disconnect error: %s", e, exc_info=True)
        return {"statusCode": 500, "body": "Internal server error"}
