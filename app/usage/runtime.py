"""Shared usage store configured from the environment."""

from app.config import get_settings
from app.usage.store import RealtimeUsagePricing, UsagePricing, UsageStore

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
    (
        RealtimeUsagePricing(
            model="gpt-realtime-2.1",
            text_input_per_million=settings.realtime_text_input_price_per_million,
            text_cached_input_per_million=(
                settings.realtime_text_cached_input_price_per_million
            ),
            text_output_per_million=settings.realtime_text_output_price_per_million,
            audio_input_per_million=settings.realtime_audio_input_price_per_million,
            audio_cached_input_per_million=(
                settings.realtime_audio_cached_input_price_per_million
            ),
            audio_output_per_million=settings.realtime_audio_output_price_per_million,
            effective_date=settings.realtime_pricing_date,
        ),
        RealtimeUsagePricing(
            model="gpt-realtime-2.1-mini",
            text_input_per_million=(
                settings.realtime_mini_text_input_price_per_million
            ),
            text_cached_input_per_million=(
                settings.realtime_mini_text_cached_input_price_per_million
            ),
            text_output_per_million=(
                settings.realtime_mini_text_output_price_per_million
            ),
            audio_input_per_million=(
                settings.realtime_mini_audio_input_price_per_million
            ),
            audio_cached_input_per_million=(
                settings.realtime_mini_audio_cached_input_price_per_million
            ),
            audio_output_per_million=(
                settings.realtime_mini_audio_output_price_per_million
            ),
            effective_date=settings.realtime_pricing_date,
        ),
    ),
)
