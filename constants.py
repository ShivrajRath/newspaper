"""Constants for newspaper generation."""

# WMO Weather Interpretation Codes → (description, emoji)
WMO_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Icy fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    61: ("Slight rain", "🌧️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    71: ("Slight snow", "❄️"),
    73: ("Moderate snow", "❄️"),
    75: ("Heavy snow", "❄️"),
    80: ("Slight showers", "🌦️"),
    81: ("Moderate showers", "🌦️"),
    82: ("Heavy showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm w/ hail", "⛈️"),
    99: ("Thunderstorm w/ heavy hail", "⛈️"),
}

# Curated word list for fallback (one per day-of-year, cycling)
FALLBACK_WORDS = [
    "ephemeral", "sonder", "serendipity", "melancholy", "luminous",
    "petrichor", "ineffable", "soliloquy", "halcyon", "querulous",
    "fugacious", "sempiternal", "laconic", "perspicacious", "ebullient",
    "recondite", "sanguine", "tenacious", "veracious", "whimsical",
    "zealous", "arcane", "benevolent", "cogent", "dauntless",
    "eloquent", "fastidious", "grandiose", "heuristic", "indefatigable",
]

FALLBACK_PUZZLES = [
    {
        "type": "riddle",
        "question": "I speak without a mouth and hear without ears. I have no body, but I come alive with the wind. What am I?",
        "answer": "An echo",
        "hint": "Think about sound bouncing back to you in a canyon."
    },
    {
        "type": "riddle",
        "question": "The more you take, the more you leave behind. What am I?",
        "answer": "Footsteps",
        "hint": "Think about walking on a trail."
    },
    {
        "type": "riddle",
        "question": "I have cities, but no houses live there. I have mountains, but no trees grow there. I have water, but no fish swim there. I have roads, but no cars drive there. What am I?",
        "answer": "A map",
        "hint": "You unfold me to find your way."
    },
    {
        "type": "riddle",
        "question": "What has hands but can't clap?",
        "answer": "A clock",
        "hint": "It helps you keep track of time."
    },
    {
        "type": "riddle",
        "question": "What gets wetter the more it dries?",
        "answer": "A towel",
        "hint": "You use it after a shower."
    },
    {
        "type": "riddle",
        "question": "I'm light as a feather, yet the strongest man can't hold me for more than a minute. What am I?",
        "answer": "Breath",
        "hint": "You do it automatically, all the time."
    },
    {
        "type": "riddle",
        "question": "What begins with T, ends with T, and has T in it?",
        "answer": "A teapot",
        "hint": "You boil water to use it."
    },
]
