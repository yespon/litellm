"""
Handles Batching + sending Httpx Post requests to feishu 
"""

from typing import TYPE_CHECKING, Any

from litellm._logging import verbose_proxy_logger

if TYPE_CHECKING:
    from .feishu_alerting import FeishuAlerting as _FeishuAlerting

    FeishuAlertingType = _FeishuAlerting
else:
    FeishuAlertingType = Any


def squash_feishu_payloads(queue):
    squashed = {}
    if len(queue) == 0:
        return squashed
    if len(queue) == 1:
        return {"key": {"item": queue[0], "count": 1}}

    for item in queue:
        url = item["url"]
        alert_type = item["alert_type"]
        _key = (url, alert_type)

        if _key in squashed:
            squashed[_key]["count"] += 1
        else:
            squashed[_key] = {"item": item, "count": 1}

    return squashed


def _print_feishu_alerting_payload_warning(
    payload: dict, feishuAlertingInstance: FeishuAlertingType
):
    if feishuAlertingInstance.alerting_args.log_to_console is True:
        verbose_proxy_logger.warning(payload)


async def send_to_feishu_webhook(feishuAlertingInstance: FeishuAlertingType, item, count):
    """
    Send a single feishu alert to the webhook
    """
    import json

    payload = item.get("payload", {})
    try:
        # Feishu interactive card or text message
        # If it's a card, we might want to add Num Alerts to the title or a field
        # For now, if count > 1, we prepend it to the text if it's a simple text message
        if count > 1:
            if "content" in payload and isinstance(payload["content"], str):
                 payload["content"] = f"[Num Alerts: {count}]\n\n{payload['content']}"
            elif "card" in payload:
                 # Add to card if possible, or just keep it simple
                 pass

        response = await feishuAlertingInstance.async_http_handler.post(
            url=item["url"],
            headers=item["headers"],
            data=json.dumps(payload),
        )
        if response.status_code != 200:
            verbose_proxy_logger.debug(
                f"Error sending feishu alert to url={item['url']}. Error={response.text}"
            )
    except Exception as e:
        verbose_proxy_logger.debug(f"Error sending feishu alert: {str(e)}")
    finally:
        _print_feishu_alerting_payload_warning(
            payload, feishuAlertingInstance=feishuAlertingInstance
        )
