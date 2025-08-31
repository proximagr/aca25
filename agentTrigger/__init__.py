import os
import openai
import logging
import azure.functions as func

openai.api_type = "azure"
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_version = "2023-07-01-preview"
openai.api_key = os.getenv("AZURE_OPENAI_KEY")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Agent triggered by telemetry")

    telemetry = req.get_json()
    prompt = f"""
    You are an infrastructure AI agent. Analyze the following telemetry and logs:
    CPU: {telemetry['cpu']}%
    Memory: {telemetry['memory']}%
    Logs: {telemetry['logs']}

    Identify the root cause and propose remediation steps.
    """

    response = openai.ChatCompletion.create(
        engine="gpt-4.1",  # Replace with your deployment name
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300
    )

    result = response['choices'][0]['message']['content']
    return func.HttpResponse(result, status_code=200)
