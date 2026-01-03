# Feishu Alerting on LiteLLM Gateway

This folder contains the Feishu (Lark) alerting integration for LiteLLM Gateway.

## Folder Structure

- `feishu_alerting.py`: Main module for sending Feishu alerts using Interactive Cards.
- `batching_handler.py`: Handles async POST requests to Feishu Webhooks with optional batching.
- `budget_alert_types.py`: Logic for different budget alert messages (Proxy, User, Team, etc.).
- `hanging_request_check.py`: Background task to alert on hanging requests.
- `utils.py`: Signature verification and environment variable processing.

## Setup

1. **Get Feishu Webhook URL**:
   Create a bot in a Feishu group and get its Webhook URL.
   Optional: Get the **Secret** for signature verification.

2. **Configure environment variables**:
   ```bash
   export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..."
   export FEISHU_SECRET="your_secret_here" # Optional but recommended
   ```

3. **Configure `config.yaml`**:
   Add `feishu` to your `alerting` list:
   ```yaml
   litellm_settings:
     alerting: ["feishu"]
     alerting_threshold: 300 # Alert if requests take > 300s
   ```

## Supported Alert Types

- `llm_exceptions`: LLM API errors.
- `llm_too_slow`: Request time exceeds `alerting_threshold`.
- `llm_requests_hanging`: Requests that haven't finished within `alerting_threshold`.
- `budget_alerts`: Budget or soft budget crossed for Keys, Users, or Teams.
- `daily_reports`: Daily summary of deployment performance (latency/failures).

## Custom Webhooks per Alert Type

You can routes different alerts to different Feishu channels:

```yaml
litellm_settings:
  alerting: ["feishu"]
  alert_to_webhook_url:
    llm_exceptions: "https://open.feishu.cn/open-apis/bot/v2/hook/EXCEPTION_CHANNEL"
    budget_alerts: "os.environ/FEISHU_BUDGET_WEBHOOK"
```
