"""Shared usage store configured from the environment."""

from app.config import get_settings
from app.usage.store import UsagePricing, UsageStore

settings = get_settings()
usage_store = UsageStore(
    settings.usage_db_path,
    UsagePricing(
        model=settings.usage_pricing_model,
        input_per_million=settings.usage_input_price_per_million,
        cached_input_per_million=settings.usage_cached_input_price_per_million,
        output_per_million=settings.usage_output_price_per_million,
        effective_date=settings.usage_pricing_date,
    ),
)
