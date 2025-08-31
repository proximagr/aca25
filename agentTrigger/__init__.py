import os
import logging
import azure.functions as func
from openai import AzureOpenAI

# Initialize AzureOpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT")  # Optional if you want to keep it dynamic
)

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

        chat_completion = client.chat.completions.create(
            model="gpt-4.1",  # This must match your deployment name
            messages=[{"role": "user", "content": prompt}]
        )

        result = chat_completion.choices[0].message.content
        return func.HttpResponse(result, status_code=200)

    except Exception as e:
        logging.error(f"Agent failed: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500)
