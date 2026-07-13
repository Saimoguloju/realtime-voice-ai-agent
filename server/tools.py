#
# Function-calling tools for the voice agent.
#
# These are Pipecat "direct functions": their JSON schema is generated from the
# signature + docstring, and they're advertised to the LLM by listing them in
# ``LLMContext(tools=[...])`` in bot.py.
#

"""Tools the LLM can invoke mid-conversation: live weather, current time, and
retrieval-augmented search over the local knowledge base."""

from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp
from loguru import logger
from pipecat.services.llm_service import FunctionCallParams

from knowledge import knowledge_base

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "moderate rain showers", 82: "violent rain showers", 95: "thunderstorm",
    96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}  # fmt: skip


async def get_current_weather(params: FunctionCallParams, city: str):
    """Get the current weather for a city, using live data.

    Args:
        city: Name of the city, e.g. "Berlin" or "New York".
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                GEOCODE_URL, params={"name": city, "count": 1}
            ) as response:
                geo = await response.json()
            results = geo.get("results")
            if not results:
                return {"error": f"Could not find a city named {city}."}
            place = results[0]

            async with session.get(
                FORECAST_URL,
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                },
            ) as response:
                forecast = await response.json()

        current = forecast["current"]
        return {
            "city": place["name"],
            "country": place.get("country"),
            "temperature_c": current["temperature_2m"],
            "humidity_percent": current["relative_humidity_2m"],
            "wind_speed_kmh": current["wind_speed_10m"],
            "conditions": WEATHER_CODES.get(current["weather_code"], "unknown"),
        }
    except Exception as e:
        logger.error(f"Weather lookup failed: {e}")
        return {"error": "The weather service is unavailable right now."}


async def get_current_time(params: FunctionCallParams, timezone: str = "UTC"):
    """Get the current date and time in a given IANA timezone.

    Args:
        timezone: IANA timezone name, e.g. "Europe/Berlin" or "America/New_York".
            Defaults to UTC.
    """
    try:
        now = datetime.now(ZoneInfo(timezone))
    except (KeyError, ValueError):
        return {"error": f"Unknown timezone {timezone}. Use an IANA name like Europe/Berlin."}
    return {
        "timezone": timezone,
        "local_time": now.strftime("%A, %B %d %Y, %I:%M %p"),
    }


async def search_knowledge_base(params: FunctionCallParams, query: str):
    """Search the company knowledge base for product, billing, security, or
    support questions. Always use this before answering questions about Nimbus.

    Args:
        query: A short natural-language search query describing what to look up.
    """
    results = await knowledge_base.search(query, top_k=3)
    if not results:
        return {"answer": "No knowledge base results found. Answer from general knowledge and say you are unsure."}
    return {"results": results}
