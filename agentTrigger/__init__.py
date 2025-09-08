import os
import json
import logging
from typing import Any, Dict

import azure.functions as func
import openai
from openai.error import OpenAIError
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from . import schemas

# Configure OpenAI for Azure via environment variables
openai.api_key = os.getenv("AZURE_OPENAI_KEY")
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")  # e.g. https://your-resource.openai.azure.com/
openai.api_type = "azure"
openai.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")  # required

# Retry configuration for transient OpenAI errors
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(OpenAIError),
)
def _call_openai_with_retry(deployment: str, prompt: str, temperature: float, max_tokens: int):
    return openai.ChatCompletion.create(
        engine=deployment,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _build_prompt(alert_data: Dict[str, Any]) -> str:
    essentials = alert_data.get("data", {}).get("essentials", {}) or {}
    context = alert_data.get("data", {}).get("alertContext", {}) or {}

    resource = essentials.get("resourceName", "unknown")
    alert_rule = essentials.get("alertRule", "")
    monitor_condition = essentials.get("monitorCondition", "")
    metric_name = (context.get("condition") or {}).get("metricName", "unknown")
    value = context.get("value", "unknown")
    timestamp = essentials.get("timeGenerated", "")

    logs = {
        "alertRule": alert_rule,
        "monitorCondition": monitor_condition,
        "raw_context": context.get("context", {}),
    }

    prompt = (
        "You are an infrastructure AI agent. Analyze the following telemetry and logs and:\n"
        "1) Provide a concise probable root cause (1-2 sentences).\n"
        "2) Provide prioritized remediation steps (3-6 bullets).\n"
        "3) Provide any follow-up checks or mitigations to collect more info.\n\n"
        f"Resource: {resource}\n"
        f"Timestamp: {timestamp}\n"
        f"Metric: {metric_name}\n"
        f"Value: {value}\n"
        f"Logs: {json.dumps(logs, default=str)}\n\n"
        "Be concise and actionable."
    )
    return prompt


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Agent triggered by Azure Monitor alert")

    if not OPENAI_DEPLOYMENT:
        logging.error("Missing AZURE_OPENAI_DEPLOYMENT environment variable")
        body = {"error": "Server misconfiguration: missing deployment name"}
        return func.HttpResponse(json.dumps(body), status_code=500, mimetype="application/json")

    try:
        # Parse request body robustly
        try:
            alert_raw = req.get_json()
        except ValueError:
            raw = req.get_body().decode("utf-8") or ""
            if not raw:
                return func.HttpResponse(
                    json.dumps({"error": "Bad request: empty body or invalid JSON"}),
                    status_code=400,
                    mimetype="application/json",
                )
            alert_raw = json.loads(raw)

        # Validate payload using pydantic
        try:
            validated = schemas.Alert.parse_obj(alert_raw)
        except ValidationError as ve:
            logging.warning("Invalid alert payload: %s", ve.json())
            return func.HttpResponse(
                json.dumps({"error": "Invalid alert payload", "details": ve.errors()}),
                status_code=400,
                mimetype="application/json",
            )

        # Build prompt and call OpenAI with retries
        prompt = _build_prompt(validated.dict())
        logging.debug("Prompt built for OpenAI call")

        response = _call_openai_with_retry(
            OPENAI_DEPLOYMENT,
            prompt,
            float(os.getenv("OPENAI_TEMPERATURE", "0.0")),
            int(os.getenv("OPENAI_MAX_TOKENS", "800")),
        )

        # Extract content safely
        ai_text = ""
        if getattr(response, "choices", None):
            choice = response.choices[0]
            if getattr(choice, "message", None):
                ai_text = choice.message.get("content", "").strip()
            else:
                # Fallback if response shape differs
                ai_text = getattr(choice, "text", "") or str(choice)
        else:
            ai_text = str(response)

        result = {"recommendation": ai_text, "deployment": OPENAI_DEPLOYMENT}
        return func.HttpResponse(json.dumps(result, ensure_ascii=False), status_code=200, mimetype="application/json")

    except OpenAIError as oe:
        logging.exception("OpenAI API error")
        return func.HttpResponse(
            json.dumps({"error": "OpenAI API error", "details": str(oe)}),
            status_code=502,
            mimetype="application/json",
        )
    except Exception:
        logging.exception("Agent failed")
        return func.HttpResponse(
            json.dumps({"error": "Internal Server Error"}), status_code=500, mimetype="application/json"
        )