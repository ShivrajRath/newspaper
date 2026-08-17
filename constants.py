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
    {
        "type": "riddle",
        "question": "I have a head and a tail but no body. What am I?",
        "answer": "A coin",
        "hint": "You flip me to make decisions."
    },
    {
        "type": "riddle",
        "question": "The more you have of me, the less you see. What am I?",
        "answer": "Darkness",
        "hint": "I appear when the lights go out."
    },
    {
        "type": "riddle",
        "question": "I have branches but no fruit, trunk, or leaves. What am I?",
        "answer": "A bank",
        "hint": "You keep your money here."
    },
    {
        "type": "riddle",
        "question": "What can you catch but not throw?",
        "answer": "A cold",
        "hint": "It comes with sneezing and a runny nose."
    },
    {
        "type": "riddle",
        "question": "I'm always in front of you but can never be seen. What am I?",
        "answer": "The future",
        "hint": "Think about time and what hasn't happened yet."
    },
    {
        "type": "riddle",
        "question": "What has one eye but cannot see?",
        "answer": "A needle",
        "hint": "Thread goes through me."
    },
    {
        "type": "riddle",
        "question": "I have keys but no locks. I have space but no room. You can enter but can't go inside. What am I?",
        "answer": "A keyboard",
        "hint": "You use me every day at a computer."
    },
    {
        "type": "riddle",
        "question": "What is always coming but never arrives?",
        "answer": "Tomorrow",
        "hint": "It becomes today the moment it gets here."
    },
    {
        "type": "riddle",
        "question": "The more you remove from me, the bigger I get. What am I?",
        "answer": "A hole",
        "hint": "Dig deeper and I grow."
    },
    {
        "type": "riddle",
        "question": "I go up when rain comes down. What am I?",
        "answer": "An umbrella",
        "hint": "You open me in a storm."
    },
    {
        "type": "riddle",
        "question": "I can be cracked, made, told, and played. What am I?",
        "answer": "A joke",
        "hint": "I make people laugh."
    },
    {
        "type": "riddle",
        "question": "I shave every day, but my beard stays the same. Who am I?",
        "answer": "A barber",
        "hint": "I shave other people, not myself."
    },
    {
        "type": "riddle",
        "question": "What has a bottom at the top?",
        "answer": "Your legs",
        "hint": "Think about your body."
    },
    {
        "type": "riddle",
        "question": "I have teeth but cannot eat. What am I?",
        "answer": "A comb",
        "hint": "You use me to style your hair."
    },
    {
        "type": "riddle",
        "question": "What word becomes shorter when you add two letters to it?",
        "answer": "Short",
        "hint": "Adding '-er' changes its meaning."
    },
    {
        "type": "riddle",
        "question": "I have no doors but have keys. I have no rooms but have space. You can enter but you cannot leave. What am I?",
        "answer": "A piano",
        "hint": "I make music with 88 keys."
    },
    {
        "type": "riddle",
        "question": "What runs but has no legs, and has a bed but never sleeps?",
        "answer": "A river",
        "hint": "It flows through the land."
    },
    {
        "type": "riddle",
        "question": "I'm full of holes but still hold water. What am I?",
        "answer": "A sponge",
        "hint": "You use me to wash dishes."
    },
    {
        "type": "riddle",
        "question": "What has four wheels and flies?",
        "answer": "A garbage truck",
        "hint": "It picks up your trash."
    },
    {
        "type": "riddle",
        "question": "I build castles yet tear down mountains. I make some men blind yet help others see. What am I?",
        "answer": "Sand",
        "hint": "You find me at the beach."
    },
    {
        "type": "riddle",
        "question": "The more I dry, the wetter I become. What am I?",
        "answer": "A towel",
        "hint": "You grab me after a shower."
    },
    {
        "type": "riddle",
        "question": "What can travel around the world while staying in a corner?",
        "answer": "A stamp",
        "hint": "You stick me on an envelope."
    },
    {
        "type": "riddle",
        "question": "I have a ring but no finger. What am I?",
        "answer": "A telephone",
        "hint": "You answer me when someone calls."
    },
    {
        "type": "riddle",
        "question": "What has a face but no eyes, nose, or mouth?",
        "answer": "A clock",
        "hint": "It tells you the time."
    },
    {
        "type": "riddle",
        "question": "I start with M, end with X, and have a never-ending list of letters. What am I?",
        "answer": "A mailbox",
        "hint": "Letters arrive here every day."
    },
    {
        "type": "riddle",
        "question": "What loses its head in the morning and gets it back at night?",
        "answer": "A pillow",
        "hint": "You rest on me while sleeping."
    },
    {
        "type": "riddle",
        "question": "I am not alive, but I grow. I don't have lungs, but I need air. What am I?",
        "answer": "Fire",
        "hint": "I give warmth and light."
    },
    {
        "type": "riddle",
        "question": "What can you hold in your right hand but never in your left?",
        "answer": "Your left hand",
        "hint": "Think literally about which hand is which."
    },
    {
        "type": "riddle",
        "question": "I live in a corner but travel the world. What am I?",
        "answer": "A stamp",
        "hint": "I sit in the corner of an envelope."
    },
    {
        "type": "riddle",
        "question": "What gets bigger the more you give away?",
        "answer": "Generosity",
        "hint": "Think about kindness and sharing."
    },
    {
        "type": "riddle",
        "question": "I have 13 hearts but no body, brain, or soul. What am I?",
        "answer": "A deck of cards",
        "hint": "You play games with me."
    },
    {
        "type": "riddle",
        "question": "I'm tall when I'm young, short when I'm old. What am I?",
        "answer": "A candle",
        "hint": "I melt as I burn."
    },
    {
        "type": "riddle",
        "question": "What has one head, one foot, and four legs?",
        "answer": "A bed",
        "hint": "You sleep in me every night."
    },
    {
        "type": "riddle",
        "question": "What comes once in a minute, twice in a moment, but never in a thousand years?",
        "answer": "The letter M",
        "hint": "Look at the words themselves."
    },
    {
        "type": "riddle",
        "question": "I have no feet, no hands, no wings, but I climb to the sky. What am I?",
        "answer": "Smoke",
        "hint": "I rise from fire."
    },
]
