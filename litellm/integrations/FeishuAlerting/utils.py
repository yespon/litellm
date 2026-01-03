"""
Utils used for feishu alerting
"""

import hashlib
import hmac
import base64
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import litellm
from litellm.proxy._types import AlertType
from litellm.secret_managers.main import get_secret

if TYPE_CHECKING:
    from litellm.litellm_core_utils.litellm_logging import Logging as _Logging

    Logging = _Logging
else:
    Logging = Any


def gen_feishu_sign(secret: str, timestamp: int) -> str:
    # sign with timestamp and secret
    string_to_sign = "{}\n{}".format(timestamp, secret)
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    return sign


def process_feishu_alerting_variables(
    alert_to_webhook_url: Optional[Dict[AlertType, Union[List[str], str]]]
) -> Optional[Dict[AlertType, Union[List[str], str]]]:
    """
    process alert_to_webhook_url
    - check if any urls are set as os.environ/FEISHU_WEBHOOK_URL_1 read env var and set the correct value
    """
    if alert_to_webhook_url is None:
        return None

    for alert_type, webhook_urls in alert_to_webhook_url.items():
        if isinstance(webhook_urls, list):
            _webhook_values: List[str] = []
            for webhook_url in webhook_urls:
                if "os.environ/" in webhook_url:
                    _env_value = get_secret(secret_name=webhook_url)
                    if not isinstance(_env_value, str):
                        raise ValueError(
                            f"Invalid webhook url value for: {webhook_url}. Got type={type(_env_value)}"
                        )
                    _webhook_values.append(_env_value)
                else:
                    _webhook_values.append(webhook_url)

            alert_to_webhook_url[alert_type] = _webhook_values
        else:
            _webhook_value_str: str = webhook_urls
            if "os.environ/" in webhook_urls:
                _env_value = get_secret(secret_name=webhook_urls)
                if not isinstance(_env_value, str):
                    raise ValueError(
                        f"Invalid webhook url value for: {webhook_urls}. Got type={type(_env_value)}"
                    )
                _webhook_value_str = _env_value
            else:
                _webhook_value_str = webhook_urls

            alert_to_webhook_url[alert_type] = _webhook_value_str

    return alert_to_webhook_url
