import os
from datetime import datetime as dt
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from litellm.types.utils import LiteLLMPydanticObjectBase

class FeishuAlertingArgs(LiteLLMPydanticObjectBase):
    daily_report_frequency: int = Field(
        default=int(
            os.getenv(
                "FEISHU_DAILY_REPORT_FREQUENCY",
                12 * 60 * 60,
            )
        ),
        description="Frequency of receiving deployment latency/failure reports. Default is 12hours. Value is in seconds.",
    )
    report_check_interval: int = Field(
        default=5 * 60,
        description="Frequency of checking cache if report should be sent. Background process. Default is once per hour. Value is in seconds.",
    )  # 5 minutes
    budget_alert_ttl: int = Field(
        default=24 * 60 * 60,
        description="Cache ttl for budgets alerts. Prevents spamming same alert, each time budget is crossed. Value is in seconds.",
    )  # 24 hours
    outage_alert_ttl: int = Field(
        default=1 * 60,
        description="Cache ttl for model outage alerts. Sets time-window for errors. Default is 1 minute. Value is in seconds.",
    )  # 1 minute ttl
    region_outage_alert_ttl: int = Field(
        default=1 * 60,
        description="Cache ttl for provider-region based outage alerts. Alert sent if 2+ models in same region report errors. Sets time-window for errors. Default is 1 minute. Value is in seconds.",
    )  # 1 minute ttl
    minor_outage_alert_threshold: int = Field(
        default=5,
        description="The number of errors that count as a model/region minor outage. ('400' error code is not counted).",
    )
    major_outage_alert_threshold: int = Field(
        default=10,
        description="The number of errors that countas a model/region major outage. ('400' error code is not counted).",
    )
    max_outage_alert_list_size: int = Field(
        default=10,
        description="Maximum number of errors to store in cache. For a given model/region. Prevents memory leaks.",
    )  # prevent memory leak
    log_to_console: bool = Field(
        default=False,
        description="If true, the alerting payload will be printed to the console.",
    )
