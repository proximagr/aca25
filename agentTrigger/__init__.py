import openai
import os
import logging
import azure.functions as func

openai.api_type = "azure"
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_version = "2024-12-01-preview"
openai.api_key = os.getenv("AZURE_OPENAI_KEY")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Agent triggered by telemetry")

    try:
        telemetry = req.get_json()
        cpu = telemetry.get("cpu", "unknown")
        memory = telemetry.get("memory", "unknown")
        logs = telemetry.get("logs", [])

        prompt = f"""
        You are an infrastructure AI agent. Analyze the following telemetry and logs:
        CPU: {cpu}%
        Memory: {memory}%
        Logs: {logs}

        Identify the root cause and propose remediation steps.
        """

        response = openai.ChatCompletion.create(
            engine="gpt-4.1",  # Must match your deployment name exactly
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )

        result = response['choices'][0]['message']['content']
        return func.HttpResponse(result, status_code=200)

    except Exception as e:
        logging.error(f"Agent failed: {str(e)}")
        return func.HttpResponse("Internal Server Error", status_code=500)
