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

# 100 Fallback Words for Word of the Day
FALLBACK_WORDS = [
    {
        "word": "serendipity",
        "part_of_speech": "noun",
        "definition": "The occurrence and development of events by chance in a happy or beneficial way.",
        "example": "Finding that rare book in a small thrift shop was pure serendipity."
    },
    {
        "word": "ephemeral",
        "part_of_speech": "adjective",
        "definition": "Lasting for a very short time; transitory.",
        "example": "The morning mist gave the landscape an ephemeral beauty that vanished with the rising sun."
    },
    {
        "word": "mellifluous",
        "part_of_speech": "adjective",
        "definition": "Sweet or musical; pleasant to hear.",
        "example": "The cello player produced a rich, mellifluous tone that resonated throughout the hall."
    },
    {
        "word": "petrichor",
        "part_of_speech": "noun",
        "definition": "A pleasant, distinctive smell that frequently accompanies the first rain after a long period of warm, dry weather.",
        "example": "As the afternoon thunderstorm broke, the sweet scent of petrichor filled the air."
    },
    {
        "word": "sonder",
        "part_of_speech": "noun",
        "definition": "The profound feeling of realizing that everyone, including strangers passing by, has a life as vivid and complex as one's own.",
        "example": "Standing on the crowded subway platform, he was struck by a quiet moment of sonder."
    },
    {
        "word": "ineffable",
        "part_of_speech": "adjective",
        "definition": "Too great or extreme to be expressed or described in words.",
        "example": "The sunset over the canyon filled her with an ineffable sense of wonder."
    },
    {
        "word": "halcyon",
        "part_of_speech": "adjective",
        "definition": "Denoting a period of time in the past that was idyllically happy and peaceful.",
        "example": "They looked back fondly on the halcyon days of their youth."
    },
    {
        "word": "quixotic",
        "part_of_speech": "adjective",
        "definition": "Exceedingly idealistic; unrealistic and impractical.",
        "example": "His quixotic quest to establish a cashless utopian colony ultimately faltered."
    },
    {
        "word": "luminescence",
        "part_of_speech": "noun",
        "definition": "The emission of light by a substance not resulting from heat.",
        "example": "The gentle luminescence of fireflies lit the summer pathway."
    },
    {
        "word": "solitude",
        "part_of_speech": "noun",
        "definition": "The state or situation of being alone, especially when pleasant or peaceful.",
        "example": "She cherished the quiet solitude of early mornings in her garden."
    },
    {
        "word": "resilience",
        "part_of_speech": "noun",
        "definition": "The capacity to withstand or to recover quickly from difficulties; toughness.",
        "example": "The community demonstrated remarkable resilience in rebuilding after the storm."
    },
    {
        "word": "ubiquitous",
        "part_of_speech": "adjective",
        "definition": "Present, appearing, or found everywhere.",
        "example": "Smartphones have become ubiquitous across every modern society."
    },
    {
        "word": "eloquent",
        "part_of_speech": "adjective",
        "definition": "Fluent or persuasive in speaking or writing.",
        "example": "The laureate delivered an eloquent speech on the power of literature."
    },
    {
        "word": "labyrinthine",
        "part_of_speech": "adjective",
        "definition": "Like a labyrinth; irregular and twisting; intricate and confusing.",
        "example": "They wandered through the labyrinthine streets of the ancient medina."
    },
    {
        "word": "perspicacity",
        "part_of_speech": "noun",
        "definition": "The quality of having a ready insight into things; shrewdness.",
        "example": "Her remarkable perspicacity allowed her to anticipate market shifts before others."
    },
    {
        "word": "magnanimous",
        "part_of_speech": "adjective",
        "definition": "Generous or forgiving, especially toward a rival or less powerful person.",
        "example": "In a magnanimous gesture, the winner congratulated his opponent on a hard-fought match."
    },
    {
        "word": "evanescent",
        "part_of_speech": "adjective",
        "definition": "Soon passing out of sight, memory, or existence; quickly fading or disappearing.",
        "example": "The rainbow was an evanescent arc across the rainy afternoon sky."
    },
    {
        "word": "panacea",
        "part_of_speech": "noun",
        "definition": "A solution or remedy for all difficulties or diseases.",
        "example": "Technology is a powerful tool, but it is not a panacea for complex social problems."
    },
    {
        "word": "sagacious",
        "part_of_speech": "adjective",
        "definition": "Having or showing keen mental discernment and good judgment; wise.",
        "example": "The company thrived under the sagacious guidance of its founding mentor."
    },
    {
        "word": "sycophant",
        "part_of_speech": "noun",
        "definition": "A person who acts obsequiously toward someone important in order to gain advantage.",
        "example": "He surrounded himself with sycophants who never questioned his decisions."
    },
    {
        "word": "effervescent",
        "part_of_speech": "adjective",
        "definition": "Vivacious and enthusiastic; giving off bubbles.",
        "example": "Her effervescent personality brought energy to every gathering."
    },
    {
        "word": "nebulous",
        "part_of_speech": "adjective",
        "definition": "In the form of a cloud or haze; hazy, indistinct, or ill-defined.",
        "example": "The project proposal remained nebulous until specific milestones were set."
    },
    {
        "word": "scintilla",
        "part_of_speech": "noun",
        "definition": "A tiny trace or spark of a specified quality or feeling.",
        "example": "There was not a scintilla of doubt left in the jury's deliberations."
    },
    {
        "word": "vicarious",
        "part_of_speech": "adjective",
        "definition": "Experienced in the imagination through the feelings or actions of another person.",
        "example": "She felt a vicarious thrill watching her daughter win the championship."
    },
    {
        "word": "lucid",
        "part_of_speech": "adjective",
        "definition": "Expressed clearly; easy to understand; bright or luminous.",
        "example": "The professor gave a lucid explanation of quantum mechanics."
    },
    {
        "word": "alacrity",
        "part_of_speech": "noun",
        "definition": "Brisk and cheerful readiness.",
        "example": "The eager apprentice accepted the assignment with alacrity."
    },
    {
        "word": "clandestine",
        "part_of_speech": "adjective",
        "definition": "Kept secret or done secretively, especially because illicit.",
        "example": "The diplomats held a clandestine meeting to negotiate peace terms."
    },
    {
        "word": "fastidious",
        "part_of_speech": "adjective",
        "definition": "Very attentive to and concerned about accuracy and detail.",
        "example": "The archivist was fastidious in cataloging historical manuscripts."
    },
    {
        "word": "idiosyncrasy",
        "part_of_speech": "noun",
        "definition": "A mode of behavior or way of thought peculiar to an individual.",
        "example": "One of his charming idiosyncrasies was drinking tea exclusively from vintage cups."
    },
    {
        "word": "tenacious",
        "part_of_speech": "adjective",
        "definition": "Tending to keep a firm hold of something; persistent and determined.",
        "example": "Her tenacious pursuit of the truth uncovered the entire story."
    },
    {
        "word": "gregarious",
        "part_of_speech": "adjective",
        "definition": "Fond of company; sociable.",
        "example": "He was a gregarious host who loved bringing together friends and strangers alike."
    },
    {
        "word": "pernicious",
        "part_of_speech": "adjective",
        "definition": "Having a harmful effect, especially in a gradual or subtle way.",
        "example": "Misinformation can have a pernicious influence on public discourse."
    },
    {
        "word": "cacophony",
        "part_of_speech": "noun",
        "definition": "A harsh, discordant mixture of sounds.",
        "example": "The morning traffic created an overwhelming cacophony of horns and sirens."
    },
    {
        "word": "equanimity",
        "part_of_speech": "noun",
        "definition": "Mental calmness, composure, and evenness of temper, especially in a difficult situation.",
        "example": "She handled the emergency with admirable equanimity."
    },
    {
        "word": "taciturn",
        "part_of_speech": "adjective",
        "definition": "Reserved or uncommunicative in speech; saying little.",
        "example": "The taciturn craftsman preferred letting his woodwork speak for itself."
    },
    {
        "word": "zenith",
        "part_of_speech": "noun",
        "definition": "The time at which something is most powerful or successful; the highest point.",
        "example": "At the zenith of her career, the architect designed world-famous landmarks."
    },
    {
        "word": "insouciance",
        "part_of_speech": "noun",
        "definition": "Casual lack of concern; indifference.",
        "example": "He faced the daunting challenge with an air of effortless insouciance."
    },
    {
        "word": "chimerical",
        "part_of_speech": "adjective",
        "definition": "Existing only as the product of unchecked imagination; fantastically visionary.",
        "example": "The economic scheme proved to be a chimerical venture that never materialized."
    },
    {
        "word": "veracity",
        "part_of_speech": "noun",
        "definition": "Conformity to facts; accuracy; habitual truthfulness.",
        "example": "The journalist meticulously checked every source to ensure the veracity of the report."
    },
    {
        "word": "querulous",
        "part_of_speech": "adjective",
        "definition": "Complaining in a petulant or whining manner.",
        "example": "The tired travelers grew querulous after several flight delays."
    },
    {
        "word": "proclivity",
        "part_of_speech": "noun",
        "definition": "A tendency to choose or do something regularly; an inclination or predisposition.",
        "example": "From an early age, she exhibited a strong proclivity for mathematics."
    },
    {
        "word": "sanguine",
        "part_of_speech": "adjective",
        "definition": "Optimistic or positive, especially in an apparently bad or difficult situation.",
        "example": "Despite initial setbacks, the team remained sanguine about the project's prospects."
    },
    {
        "word": "superfluous",
        "part_of_speech": "adjective",
        "definition": "Unnecessary, especially through being more than enough.",
        "example": "The editor trimmed all superfluous adjectives from the opening chapter."
    },
    {
        "word": "anomaly",
        "part_of_speech": "noun",
        "definition": "Something that deviates from what is standard, normal, or expected.",
        "example": "The sudden spike in winter temperatures was a meteorological anomaly."
    },
    {
        "word": "trenchant",
        "part_of_speech": "adjective",
        "definition": "Vigorous or incisive in expression or style.",
        "example": "His trenchant criticism of the policy sparked widespread debate."
    },
    {
        "word": "capricious",
        "part_of_speech": "adjective",
        "definition": "Given to sudden and unaccountable changes of mood or behavior.",
        "example": "The coastal climate was capricious, shifting from sunshine to gales within hours."
    },
    {
        "word": "harbinger",
        "part_of_speech": "noun",
        "definition": "A person or thing that announces or signals the approach of another.",
        "example": "The blooming of crocuses is a welcome harbinger of spring."
    },
    {
        "word": "esoteric",
        "part_of_speech": "adjective",
        "definition": "Intended for or likely to be understood by only a small number of people with specialized knowledge.",
        "example": "The philosophical treatise delved into esoteric concepts of metaphysics."
    },
    {
        "word": "pellucid",
        "part_of_speech": "adjective",
        "definition": "Translucently clear; easily understood.",
        "example": "The mountain stream had pellucid waters where smooth pebbles shimmered below."
    },
    {
        "word": "enigma",
        "part_of_speech": "noun",
        "definition": "A person or thing that is mysterious, puzzling, or difficult to understand.",
        "example": "The origin of the ancient inscription remains an enigma to historians."
    },
    {
        "word": "surreptitious",
        "part_of_speech": "adjective",
        "definition": "Kept secret, especially because it would not be approved of.",
        "example": "He cast a surreptitious glance at his watch during the lengthy lecture."
    },
    {
        "word": "austere",
        "part_of_speech": "adjective",
        "definition": "Severe or strict in manner, attitude, or appearance; having no comforts or luxuries.",
        "example": "The monastery was built in an austere architectural style."
    },
    {
        "word": "zeitgeist",
        "part_of_speech": "noun",
        "definition": "The defining spirit or mood of a particular period of history as shown by the ideas and beliefs of the time.",
        "example": "The novel captured the technological zeitgeist of the early internet era."
    },
    {
        "word": "ebullient",
        "part_of_speech": "adjective",
        "definition": "Cheerful and full of energy.",
        "example": "The ebullient crowd cheered enthusiastically as the fireworks lit the sky."
    },
    {
        "word": "truculent",
        "part_of_speech": "adjective",
        "definition": "Eager or quick to argue or fight; aggressively defiant.",
        "example": "The truculent debater challenged every point made by his opponent."
    },
    {
        "word": "munificent",
        "part_of_speech": "adjective",
        "definition": "More generous than is usual or necessary.",
        "example": "The museum received a munificent endowment from an anonymous benefactor."
    },
    {
        "word": "voracious",
        "part_of_speech": "adjective",
        "definition": "Wanting or devouring great quantities of food; having a very eager approach to an activity.",
        "example": "As a voracious reader, she finished several novels every week."
    },
    {
        "word": "aesthetic",
        "part_of_speech": "adjective",
        "definition": "Concerned with beauty or the appreciation of beauty.",
        "example": "The clean lines of the furniture offered high aesthetic appeal."
    },
    {
        "word": "serene",
        "part_of_speech": "adjective",
        "definition": "Calm, peaceful, and untroubled; tranquil.",
        "example": "A serene calmness settled over the lake at twilight."
    },
    {
        "word": "garrulous",
        "part_of_speech": "adjective",
        "definition": "Excessively talkative, especially on trivial matters.",
        "example": "The garrulous cab driver shared stories throughout the entire cross-town trip."
    },
    {
        "word": "intrepid",
        "part_of_speech": "adjective",
        "definition": "Fearless; adventurous.",
        "example": "The intrepid explorer ventured deep into uncharted polar regions."
    },
    {
        "word": "catalyst",
        "part_of_speech": "noun",
        "definition": "A person or thing that precipitates an event or change.",
        "example": "The speech served as a catalyst for widespread educational reform."
    },
    {
        "word": "immutable",
        "part_of_speech": "adjective",
        "definition": "Unchanging over time or unable to be changed.",
        "example": "The fundamental laws of physics remain immutable across the cosmos."
    },
    {
        "word": "placid",
        "part_of_speech": "adjective",
        "definition": "Not easily upset or excited; calm and peaceful.",
        "example": "The placid surface of the pond mirrored the surrounding willows."
    },
    {
        "word": "fortuitous",
        "part_of_speech": "adjective",
        "definition": "Happening by accident or chance rather than design; fortunate.",
        "example": "Their fortuitous encounter at the conference led to a fruitful collaboration."
    },
    {
        "word": "reticent",
        "part_of_speech": "adjective",
        "definition": "Not revealing one's thoughts or feelings readily.",
        "example": "He remained reticent about his past achievements, preferring modesty."
    },
    {
        "word": "candid",
        "part_of_speech": "adjective",
        "definition": "Truthful and straightforward; frank.",
        "example": "The CEO gave a candid assessment of the quarter's financial hurdles."
    },
    {
        "word": "deleterious",
        "part_of_speech": "adjective",
        "definition": "Causing harm or damage.",
        "example": "Prolonged sleep deprivation has deleterious effects on cognitive performance."
    },
    {
        "word": "astute",
        "part_of_speech": "adjective",
        "definition": "Having or showing an ability to accurately assess situations or people and turn this to one's advantage.",
        "example": "His astute business sense helped the startup navigate economic turbulence."
    },
    {
        "word": "lucrative",
        "part_of_speech": "adjective",
        "definition": "Producing a great deal of profit.",
        "example": "The software engineer secured a lucrative consulting contract."
    },
    {
        "word": "tenet",
        "part_of_speech": "noun",
        "definition": "A principle or belief, especially one of the main principles of a religion or philosophy.",
        "example": "Respect for diversity is a central tenet of the organization's charter."
    },
    {
        "word": "epiphany",
        "part_of_speech": "noun",
        "definition": "A moment of sudden revelation or insight.",
        "example": "While taking a long walk, he had an epiphany that solved the mathematical dilemma."
    },
    {
        "word": "juxtaposition",
        "part_of_speech": "noun",
        "definition": "The fact of two things being seen or placed close together with contrasting effect.",
        "example": "The juxtaposition of modern skyscrapers beside historic cathedrals created striking imagery."
    },
    {
        "word": "ubiquity",
        "part_of_speech": "noun",
        "definition": "The state or capacity of being everywhere, especially at the same time; omnipresence.",
        "example": "The ubiquity of internet connectivity has revolutionized remote work."
    },
    {
        "word": "succinct",
        "part_of_speech": "adjective",
        "definition": "Briefly and clearly expressed.",
        "example": "The executive summary provided a succinct overview of the five-year plan."
    },
    {
        "word": "reverie",
        "part_of_speech": "noun",
        "definition": "A state of being pleasantly lost in one's thoughts; a daydream.",
        "example": "She was jarred from her quiet reverie by the sound of the doorbell."
    },
    {
        "word": "pragmatic",
        "part_of_speech": "adjective",
        "definition": "Dealing with things sensibly and realistically in a way that is based on practical rather than theoretical considerations.",
        "example": "They adopted a pragmatic approach to resolve the budget deficit."
    },
    {
        "word": "paradigm",
        "part_of_speech": "noun",
        "definition": "A typical example or pattern of something; a model.",
        "example": "The discovery prompted a paradigm shift in medical research."
    },
    {
        "word": "sonorous",
        "part_of_speech": "adjective",
        "definition": "Imposingly deep and full.",
        "example": "His sonorous voice carried effortlessly to the back of the auditorium."
    },
    {
        "word": "luminous",
        "part_of_speech": "adjective",
        "definition": "Full of or shedding light; bright or shining, especially in the dark.",
        "example": "The full moon cast a luminous glow over the quiet valley."
    },
    {
        "word": "benevolent",
        "part_of_speech": "adjective",
        "definition": "Well meaning and kindly; serving a charitable rather than a profit-making purpose.",
        "example": "The benevolent patron funded scholarships for underprivileged students."
    },
    {
        "word": "circumspect",
        "part_of_speech": "adjective",
        "definition": "Wary and unwilling to take risks.",
        "example": "The officials were circumspect in their statements to the press."
    },
    {
        "word": "scrupulous",
        "part_of_speech": "adjective",
        "definition": "Diligent, thorough, and extremely attentive to details.",
        "example": "The accountant took scrupulous care in balancing the ledger."
    },
    {
        "word": "verve",
        "part_of_speech": "noun",
        "definition": "Vigor and spirit or enthusiasm.",
        "example": "The orchestra performed the symphony with tremendous verve."
    },
    {
        "word": "conundrum",
        "part_of_speech": "noun",
        "definition": "A confusing and difficult problem or question.",
        "example": "Balancing urban expansion with environmental conservation is a modern conundrum."
    },
    {
        "word": "zealous",
        "part_of_speech": "adjective",
        "definition": "Having or showing zeal; passionate and fervent.",
        "example": "The zealous volunteers worked tirelessly to restore the community park."
    },
    {
        "word": "aplomb",
        "part_of_speech": "noun",
        "definition": "Self-confidence or assurance, especially when in a demanding situation.",
        "example": "She handled the unexpected technical glitch with remarkable aplomb."
    },
    {
        "word": "affable",
        "part_of_speech": "adjective",
        "definition": "Friendly, good-natured, or easy to talk to.",
        "example": "The new dean was an affable administrator who maintained an open-door policy."
    },
    {
        "word": "cogent",
        "part_of_speech": "adjective",
        "definition": "Clear, logical, and convincing.",
        "example": "The attorney presented a cogent argument that swayed the court."
    },
    {
        "word": "deft",
        "part_of_speech": "adjective",
        "definition": "Neatly skillful and quick in one's movements.",
        "example": "With deft strokes of the brush, the artist brought the canvas to life."
    },
    {
        "word": "equitable",
        "part_of_speech": "adjective",
        "definition": "Fair and impartial.",
        "example": "The committee worked to establish an equitable distribution of resources."
    },
    {
        "word": "fecund",
        "part_of_speech": "adjective",
        "definition": "Producing or capable of producing an abundance of offspring or new growth; fertile.",
        "example": "The artist possessed a fecund imagination that produced hundreds of original works."
    },
    {
        "word": "germane",
        "part_of_speech": "adjective",
        "definition": "Relevant to a subject under consideration.",
        "example": "Please keep your comments germane to the topic on the agenda."
    },
    {
        "word": "hegemony",
        "part_of_speech": "noun",
        "definition": "Leadership or dominance, especially by one country or social group over others.",
        "example": "The historical study analyzed the economic hegemony of maritime trade empires."
    },
    {
        "word": "implacable",
        "part_of_speech": "adjective",
        "definition": "Unable to be placated; relentless; unstoppable.",
        "example": "The vessel pushed forward against the implacable force of the arctic winds."
    },
    {
        "word": "judicious",
        "part_of_speech": "adjective",
        "definition": "Having, showing, or done with good judgment or sense.",
        "example": "Through judicious investing, they secured their long-term financial freedom."
    },
    {
        "word": "kinetic",
        "part_of_speech": "adjective",
        "definition": "Relating to or resulting from motion; characterized by movement.",
        "example": "The modern dance performance was filled with kinetic vibrancy."
    },
    {
        "word": "limpid",
        "part_of_speech": "adjective",
        "definition": "Free of anything that darkens; completely clear.",
        "example": "The limpid blue waters of the lagoon revealed schools of tropical fish."
    },
    {
        "word": "malleable",
        "part_of_speech": "adjective",
        "definition": "Able to be hammered or pressed permanently out of shape without breaking or cracking; easily influenced.",
        "example": "Gold is one of the most malleable metals known to metallurgy."
    },
    {
        "word": "nascent",
        "part_of_speech": "adjective",
        "definition": "Just coming into existence and beginning to display signs of future potential.",
        "example": "The nascent artificial intelligence industry is evolving at breakneck speed."
    }
]
