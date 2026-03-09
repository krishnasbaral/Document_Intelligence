from functools import lru_cache
from openai import AzureOpenAI
from app.settings import settings


@lru_cache(maxsize=1)
def get_azure_client():
    client = AzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    )
    return client, settings.AZURE_DEPLOYMENT_NAME
