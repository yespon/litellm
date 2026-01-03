"""
Class to check for LLM API hanging requests for Feishu
"""

import asyncio
from typing import TYPE_CHECKING, Any, Optional

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.caching.in_memory_cache import InMemoryCache
from litellm.litellm_core_utils.core_helpers import get_litellm_metadata_from_kwargs
from litellm.types.integrations.slack_alerting import (
    HANGING_ALERT_BUFFER_TIME_SECONDS,
    MAX_OLDEST_HANGING_REQUESTS_TO_CHECK,
    HangingRequestData,
)

if TYPE_CHECKING:
    from .feishu_alerting import FeishuAlerting as _FeishuAlerting
    FeishuAlertingType = _FeishuAlerting
else:
    FeishuAlertingType = Any


class AlertingHangingRequestCheck:
    """
    Class to safely handle checking hanging requests alerts for Feishu
    """

    def __init__(
        self,
        feishu_alerting_object: FeishuAlertingType,
    ):
        self.feishu_alerting_object = feishu_alerting_object
        self.hanging_request_cache = InMemoryCache(
            default_ttl=int(
                self.feishu_alerting_object.alerting_threshold
                + HANGING_ALERT_BUFFER_TIME_SECONDS
            ),
        )

    async def add_request_to_hanging_request_check(
        self,
        request_data: Optional[dict] = None,
    ):
        if request_data is None:
            return

        request_metadata = get_litellm_metadata_from_kwargs(kwargs=request_data)
        model = request_data.get("model", "")
        api_base: Optional[str] = None

        if request_data.get("deployment", None) is not None and isinstance(
            request_data["deployment"], dict
        ):
            api_base = litellm.get_api_base(
                model=model,
                optional_params=request_data["deployment"].get("litellm_params", {}),
            )

        hanging_request_data = HangingRequestData(
            request_id=request_data.get("litellm_call_id", ""),
            model=model,
            api_base=api_base,
            key_alias=request_metadata.get("user_api_key_alias", ""),
            team_alias=request_metadata.get("user_api_key_team_alias", ""),
        )

        await self.hanging_request_cache.async_set_cache(
            key=hanging_request_data.request_id,
            value=hanging_request_data,
            ttl=int(
                self.feishu_alerting_object.alerting_threshold
                + HANGING_ALERT_BUFFER_TIME_SECONDS
            ),
        )

    async def send_alerts_for_hanging_requests(self):
        from litellm.proxy.proxy_server import proxy_logging_obj

        if proxy_logging_obj.internal_usage_cache is None:
            return

        hanging_requests = await self.hanging_request_cache.async_get_oldest_n_keys(
            n=MAX_OLDEST_HANGING_REQUESTS_TO_CHECK,
        )

        for request_id in hanging_requests:
            hanging_request_data: Optional[HangingRequestData] = (
                await self.hanging_request_cache.async_get_cache(
                    key=request_id,
                )
            )

            if hanging_request_data is None:
                continue

            request_status = (
                await proxy_logging_obj.internal_usage_cache.async_get_cache(
                    key="request_status:{}".format(hanging_request_data.request_id),
                    litellm_parent_otel_span=None,
                    local_only=True,
                )
            )
            if request_status is not None:
                self.hanging_request_cache._remove_key(
                    key=request_id,
                )
                continue

            await self.send_hanging_request_alert(
                hanging_request_data=hanging_request_data
            )

    async def check_for_hanging_requests(self):
        while True:
            verbose_proxy_logger.debug("Checking for hanging requests (Feishu)....")
            await self.send_alerts_for_hanging_requests()
            await asyncio.sleep(self.feishu_alerting_object.alerting_threshold / 2)

    async def send_hanging_request_alert(
        self,
        hanging_request_data: HangingRequestData,
    ):
        from litellm.proxy._types import AlertType

        request_info = f"""**Request Model:** `{hanging_request_data.model}`
**API Base:** `{hanging_request_data.api_base}`
**Key Alias:** `{hanging_request_data.key_alias}`
**Team Alias:** `{hanging_request_data.team_alias}`"""

        alerting_message = f"**Requests are hanging** - `{self.feishu_alerting_object.alerting_threshold}s+` request time"
        await self.feishu_alerting_object.send_alert(
            message=alerting_message + "\n\n" + request_info,
            level="Medium",
            alert_type=AlertType.llm_requests_hanging,
            alerting_metadata=hanging_request_data.alerting_metadata or {},
        )
