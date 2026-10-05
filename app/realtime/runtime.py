"""Shared Realtime usage recorder."""

from app.realtime.usage import RealtimeUsageRecorder
from app.usage.runtime import usage_store

realtime_usage_recorder = RealtimeUsageRecorder(usage_store)
