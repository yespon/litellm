import asyncio
import datetime
import os
import random
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.caching.caching import DualCache
from litellm.integrations.custom_batch_logger import CustomBatchLogger
from litellm.proxy._types import AlertType, CallInfo, Litellm_EntityType, WebhookEvent
from litellm.litellm_core_utils.exception_mapping_utils import (
    _add_key_name_and_team_to_alert,
)
from litellm.llms.custom_httpx.http_handler import (
    get_async_httpx_client,
    httpxSpecialProvider,
)
from litellm.types.integrations.feishu_alerting import *
from litellm.types.integrations.slack_alerting import (
    DEFAULT_ALERT_TYPES,
    DeploymentMetrics,
    SlackAlertingCacheKeys,
)

from .budget_alert_types import get_budget_alert_type
# from .hanging_request_check import AlertingHangingRequestCheck # Circular import if not careful
from .utils import gen_feishu_sign, process_feishu_alerting_variables
from .batching_handler import send_to_feishu_webhook, squash_feishu_payloads

if TYPE_CHECKING:
    from litellm.router import Router as _Router
    Router = _Router
else:
    Router = Any

class FeishuAlerting(CustomBatchLogger):
    """
    Class for sending Feishu Alerts
    """

    def __init__(
        self,
        internal_usage_cache: Optional[DualCache] = None,
        alerting_threshold: Optional[float] = None,
        alerting: Optional[List] = [],
        alert_types: List[AlertType] = DEFAULT_ALERT_TYPES,
        alert_to_webhook_url: Optional[Dict[AlertType, Union[List[str], str]]] = None,
        alerting_args={},
        default_webhook_url: Optional[str] = None,
        **kwargs,
    ):
        if alerting_threshold is None:
            alerting_threshold = 300
        self.alerting_threshold = alerting_threshold
        self.alerting = alerting
        self.alert_types = alert_types
        self.internal_usage_cache = internal_usage_cache or DualCache()
        self.async_http_handler = get_async_httpx_client(
            llm_provider=httpxSpecialProvider.LoggingCallback
        )
        self.alert_to_webhook_url = process_feishu_alerting_variables(
            alert_to_webhook_url=alert_to_webhook_url
        )
        self.is_running = False
        self.alerting_args = FeishuAlertingArgs(**alerting_args)
        self.default_webhook_url = default_webhook_url
        self.flush_lock = asyncio.Lock()
        self.periodic_started = False
        
        # Late import to avoid circular dependency
        from .hanging_request_check import AlertingHangingRequestCheck
        self.hanging_request_check = AlertingHangingRequestCheck(
            feishu_alerting_object=self,
        )
        super().__init__(**kwargs, flush_lock=self.flush_lock)

    def update_values(
        self,
        alerting: Optional[List] = None,
        alerting_threshold: Optional[float] = None,
        alert_types: Optional[List[AlertType]] = None,
        alert_to_webhook_url: Optional[Dict[AlertType, Union[List[str], str]]] = None,
        alerting_args: Optional[Dict] = None,
        llm_router: Optional[Router] = None,
    ):
        if alerting is not None:
            self.alerting = alerting
            if not self.periodic_started:
                asyncio.create_task(self.periodic_flush())
                self.periodic_started = True
        if alerting_threshold is not None:
            self.alerting_threshold = alerting_threshold
        if alert_types is not None:
            self.alert_types = alert_types
        if alerting_args is not None:
            self.alerting_args = FeishuAlertingArgs(**alerting_args)
            if not self.periodic_started:
                asyncio.create_task(self.periodic_flush())
                self.periodic_started = True

        if alert_to_webhook_url is not None:
            if self.alert_to_webhook_url is None:
                self.alert_to_webhook_url = process_feishu_alerting_variables(
                    alert_to_webhook_url=alert_to_webhook_url
                )
            else:
                _new_values = (
                    process_feishu_alerting_variables(
                        alert_to_webhook_url=alert_to_webhook_url
                    )
                    or {}
                )
                self.alert_to_webhook_url.update(_new_values)
        if llm_router is not None:
            self.llm_router = llm_router

    def _prepare_feishu_card(
        self,
        title: str,
        message: str,
        level: Literal["Low", "Medium", "High"],
        alerting_metadata: dict = {},
    ) -> dict:
        """
        Prepare Feishu Interactive Card payload
        """
        template_colors = {
            "High": "red",
            "Medium": "orange",
            "Low": "blue",
        }
        timestamp = int(time.time())
        secret = os.getenv("FEISHU_SECRET")
        
        card_content = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": template_colors.get(level, "blue"),
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": message},
                }
            ],
        }
        
        payload = {
            "msg_type": "interactive",
            "card": card_content,
        }
        
        if secret:
            payload["timestamp"] = str(timestamp)
            payload["sign"] = gen_feishu_sign(secret, timestamp)
            
        return payload

    async def send_alert(
        self,
        message: str,
        level: Literal["Low", "Medium", "High"],
        alert_type: AlertType,
        alerting_metadata: dict,
        user_info: Optional[WebhookEvent] = None,
        **kwargs,
    ):
        if self.alerting is None:
            return

        if "feishu" not in self.alerting:
            return

        feishu_webhook_url = None
        if self.alert_to_webhook_url is not None:
            feishu_webhook_url = self.alert_to_webhook_url.get(alert_type) or self.alert_to_webhook_url.get("default")
        
        if feishu_webhook_url is None:
            feishu_webhook_url = self.default_webhook_url or os.getenv("FEISHU_WEBHOOK_URL")

        if feishu_webhook_url is None:
            return

        title = f"LiteLLM {alert_type.value.replace('_', ' ').title()} Alert"
        payload = self._prepare_feishu_card(
            title=title,
            message=message,
            level=level,
            alerting_metadata=alerting_metadata,
        )

        headers = {"Content-Type": "application/json"}

        if isinstance(feishu_webhook_url, list):
            for url in feishu_webhook_url:
                self.log_queue.append(
                    {
                        "url": url,
                        "headers": headers,
                        "payload": payload,
                        "alert_type": alert_type,
                    }
                )
        else:
            self.log_queue.append(
                {
                    "url": feishu_webhook_url,
                    "headers": headers,
                    "payload": payload,
                    "alert_type": alert_type,
                }
            )

        if len(self.log_queue) >= self.batch_size:
            await self.flush_queue()

    async def async_send_batch(self):
        if not self.log_queue:
            return

        squashed_queue = squash_feishu_payloads(self.log_queue)
        tasks = [
            send_to_feishu_webhook(
                feishuAlertingInstance=self, item=item["item"], count=item["count"]
            )
            for item in squashed_queue.values()
        ]
        await asyncio.gather(*tasks)
        self.log_queue.clear()

    async def response_taking_too_long_callback(self, kwargs, completion_response, start_time, end_time):
        if self.alerting is None or self.alert_types is None:
            return
        
        time_difference = end_time - start_time
        time_difference_float = time_difference.total_seconds()
        
        if time_difference_float > self.alerting_threshold:
            litellm_params = kwargs.get("litellm_params", {})
            model = kwargs.get("model", "")
            api_base = litellm.get_api_base(model=model, optional_params=litellm_params)
            
            request_info = f"\n**Request Model:** `{model}`\n**API Base:** `{api_base}`"
            slow_message = f"**Responses are slow** - `{round(time_difference_float,2)}s` response time > Alerting threshold: `{self.alerting_threshold}s`"
            
            alerting_metadata = {}
            if "metadata" in litellm_params:
                _metadata = litellm_params["metadata"]
                request_info = _add_key_name_and_team_to_alert(request_info=request_info, metadata=_metadata)
                if "alerting_metadata" in _metadata:
                    alerting_metadata = _metadata["alerting_metadata"]
            
            await self.send_alert(
                message=slow_message + request_info,
                level="Low",
                alert_type=AlertType.llm_too_slow,
                alerting_metadata=alerting_metadata,
            )

    async def budget_alerts(self, type: str, user_info: CallInfo):
        if self.alerting is None or "budget_alerts" not in self.alert_types:
            return

        budget_alert_class = get_budget_alert_type(type)
        event_message = budget_alert_class.get_event_message()
        user_info_str = self._get_user_info_str(user_info)

        await self.send_alert(
            message=f"**{event_message}**\n\n{user_info_str}",
            level="High",
            alert_type=AlertType.budget_alerts,
            alerting_metadata={},
        )

    async def async_update_daily_reports(
        self, deployment_metrics: DeploymentMetrics
    ) -> int:
        return_val = 0
        try:
            if deployment_metrics.failed_request:
                await self.internal_usage_cache.async_increment_cache(
                    key="{}:{}".format(
                        deployment_metrics.id,
                        SlackAlertingCacheKeys.failed_requests_key.value,
                    ),
                    value=1,
                    parent_otel_span=None,
                )
                return_val += 1

            if deployment_metrics.latency_per_output_token is not None:
                await self.internal_usage_cache.async_increment_cache(
                    key="{}:{}".format(
                        deployment_metrics.id, SlackAlertingCacheKeys.latency_key.value
                    ),
                    value=deployment_metrics.latency_per_output_token,
                    parent_otel_span=None,
                )
                return_val += 1
            return return_val
        except Exception:
            return 0

    async def send_daily_reports(self, router) -> bool:
        ids = router.get_model_ids()
        failed_request_keys = ["{}:{}".format(id, SlackAlertingCacheKeys.failed_requests_key.value) for id in ids]
        latency_keys = ["{}:{}".format(id, SlackAlertingCacheKeys.latency_key.value) for id in ids]
        combined_metrics_keys = failed_request_keys + latency_keys
        combined_metrics_values = await self.internal_usage_cache.async_batch_get_cache(keys=combined_metrics_keys)

        if combined_metrics_values is None:
            return False

        all_none = True
        for val in combined_metrics_values:
            if val is not None and val > 0:
                all_none = False
                break
        if all_none:
            return False

        failed_request_values = combined_metrics_values[:len(failed_request_keys)]
        latency_values = combined_metrics_values[len(failed_request_keys):]

        replaced_failed_values = [v if v is not None else 0 for v in failed_request_values]
        top_5_failed = sorted(range(len(replaced_failed_values)), key=lambda i: replaced_failed_values[i], reverse=True)[:5]
        top_5_failed = [i for i in top_5_failed if replaced_failed_values[i] > 0]

        replaced_slowest_values = [v if v is not None else 0 for v in latency_values]
        top_5_slowest = sorted(range(len(replaced_slowest_values)), key=lambda i: replaced_slowest_values[i], reverse=True)[:5]
        top_5_slowest = [i for i in top_5_slowest if replaced_slowest_values[i] > 0]

        message = "**Daily Report Summary** 📈\n\n"
        message += "**Top Deployments with Most Failed Requests:**\n"
        if not top_5_failed:
            message += "- None\n"
        for i, idx in enumerate(top_5_failed):
            key = failed_request_keys[idx].split(":")[0]
            _deployment = router.get_model_info(key)
            deployment_name = _deployment["litellm_params"].get("model", "") if isinstance(_deployment, dict) else ""
            api_base = litellm.get_api_base(model=deployment_name, optional_params=_deployment["litellm_params"] if isinstance(_deployment, dict) else {})
            message += f"{i+1}. `{deployment_name}`: {replaced_failed_values[idx]} failures (`{api_base}`)\n"

        message += "\n**Top Slowest Deployments:**\n"
        if not top_5_slowest:
            message += "- None\n"
        for i, idx in enumerate(top_5_slowest):
            key = latency_keys[idx].split(":")[0]
            _deployment = router.get_model_info(key)
            deployment_name = _deployment["litellm_params"].get("model", "") if isinstance(_deployment, dict) else ""
            api_base = litellm.get_api_base(model=deployment_name, optional_params=_deployment["litellm_params"] if isinstance(_deployment, dict) else {})
            message += f"{i+1}. `{deployment_name}`: {round(replaced_slowest_values[idx], 3)}s/token (`{api_base}`)\n"

        await self.send_alert(message=message, level="Low", alert_type=AlertType.daily_reports, alerting_metadata={})
        return True

    async def _run_scheduler_helper(self, llm_router) -> bool:
        report_sent_key = "feishu_daily_metrics_report_sent" # Use specific key for Feishu if needed, or share with Slack
        report_sent = await self.internal_usage_cache.async_get_cache(key=report_sent_key)
        current_time = time.time()
        if report_sent is None or current_time - report_sent >= self.alerting_args.daily_report_frequency:
            await self.send_daily_reports(router=llm_router)
            await self.internal_usage_cache.async_set_cache(key=report_sent_key, value=current_time)
            return True
        return False

    async def _run_scheduled_daily_report(self, llm_router: Optional[Any] = None):
        if llm_router is None or self.alert_types is None:
            return
        if "daily_reports" in self.alert_types:
            while True:
                await self._run_scheduler_helper(llm_router=llm_router)
                interval = random.randint(self.alerting_args.report_check_interval - 3, self.alerting_args.report_check_interval + 3)
                await asyncio.sleep(interval)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            if "daily_reports" in self.alert_types:
                litellm_params = kwargs.get("litellm_params", {}) or {}
                model_info = litellm_params.get("model_info", {}) or {}
                model_id = model_info.get("id", "") or ""
                response_s: timedelta = end_time - start_time
                final_value = response_s.total_seconds()
                if isinstance(response_obj, litellm.ModelResponse) and hasattr(response_obj, "usage") and response_obj.usage:
                    completion_tokens = getattr(response_obj.usage, "completion_tokens", 0)
                    if completion_tokens and completion_tokens > 0:
                        final_value = response_s.total_seconds() / completion_tokens
                await self.async_update_daily_reports(DeploymentMetrics(id=model_id, failed_request=False, latency_per_output_token=final_value, updated_at=litellm.utils.get_utc_datetime()))
        except Exception as e:
            verbose_proxy_logger.error(f"[Non-Blocking Error] Feishu Alerting: {str(e)}")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        try:
            if "daily_reports" in self.alert_types:
                litellm_params = kwargs.get("litellm_params", {}) or {}
                model_info = litellm_params.get("model_info", {}) or {}
                model_id = model_info.get("id", "") or ""
                await self.async_update_daily_reports(DeploymentMetrics(id=model_id, failed_request=True, latency_per_output_token=None, updated_at=litellm.utils.get_utc_datetime()))
        except Exception:
            pass

    async def send_weekly_spend_report(self, time_range: str = "7d"):
        if self.alerting is None or "spend_reports" not in self.alert_types or "feishu" not in self.alerting:
            return
        try:
            from litellm.proxy.spend_tracking.spend_management_endpoints import _get_spend_report_for_time_range
            days = int(time_range[:-1])
            todays_date = datetime.datetime.now().date()
            start_date = todays_date - datetime.timedelta(days=days)
            _resp = await _get_spend_report_for_time_range(start_date=start_date.strftime("%Y-%m-%d"), end_date=todays_date.strftime("%Y-%m-%d"))
            if _resp is None:
                return
            spend_per_team, spend_per_tag = _resp
            message = f"**💸 Spend Report ({start_date} to {todays_date})**\n"
            if spend_per_team:
                message += "\n**Team Spend:**\n"
                for s in spend_per_team:
                    message += f"- Team: `{s['team_alias']}` | Spend: `${round(float(s['total_spend']), 4)}`\n"
            if spend_per_tag:
                message += "\n**Tag Spend:**\n"
                for s in spend_per_tag:
                    message += f"- Tag: `{s['individual_request_tag']}` | Spend: `${round(float(s['total_spend']), 4)}`\n"
            await self.send_alert(message=message, level="Low", alert_type=AlertType.spend_reports, alerting_metadata={})
        except Exception as e:
            verbose_proxy_logger.error(f"Feishu Spend Report Error: {e}")

    async def send_monthly_spend_report(self):
        if self.alerting is None or "spend_reports" not in self.alert_types or "feishu" not in self.alerting:
            return
        try:
            from calendar import monthrange
            from litellm.proxy.spend_tracking.spend_management_endpoints import _get_spend_report_for_time_range
            todays_date = datetime.datetime.now().date()
            first_day = todays_date.replace(day=1)
            _, last_day_num = monthrange(todays_date.year, todays_date.month)
            last_day = first_day + datetime.timedelta(days=last_day_num - 1)
            _resp = await _get_spend_report_for_time_range(start_date=first_day.strftime("%Y-%m-%d"), end_date=last_day.strftime("%Y-%m-%d"))
            if _resp is None:
                return
            spend_per_team, spend_per_tag = _resp
            message = f"**📅 Monthly Spend Report ({first_day} to {last_day})**\n"
            if spend_per_team:
                message += "\n**Team Spend:**\n"
                for s in spend_per_team:
                    message += f"- Team: `{s['team_alias']}` | Spend: `${round(float(s['total_spend']), 4)}`\n"
            await self.send_alert(message=message, level="Low", alert_type=AlertType.spend_reports, alerting_metadata={})
        except Exception as e:
            verbose_proxy_logger.error(f"Feishu Monthly Spend Report Error: {e}")

    async def send_fallback_stats_from_prometheus(self):
        if self.alerting is None or "fallback_reports" not in self.alert_types or "feishu" not in self.alerting:
            return
        try:
            # This is a complex one that requires Prometheus integration.
            # Mirroring Slack's logic if possible, but keeping it simplified.
            pass
        except Exception as e:
            verbose_proxy_logger.error(f"Feishu Prometheus Report Error: {e}")

    def _get_user_info_str(self, user_info: CallInfo) -> str:
        _all_fields_as_dict = user_info.model_dump(exclude_none=True)
        if "token" in _all_fields_as_dict:
            _all_fields_as_dict.pop("token")
        msg = ""
        for k, v in _all_fields_as_dict.items():
            if isinstance(v, Litellm_EntityType):
                v = v.value
            msg += f"**{k}:** `{v}`\n"
        return msg
