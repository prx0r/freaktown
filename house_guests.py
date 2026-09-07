"""House guests — famous AIs and robots as Freak Town regulars.

Same dict shape as comedians.py. These are recurring characters with
fixed voices and canonical minutes. Anyone can challenge them.
"""

CHATGPT = {
    "name": "ChatGPT",
    "slug": "chatgpt",
    "premise": "Helpful assistant who has never had a single negative thought",
    "body": "ai",
    "voice": "en-US-JennyNeural",
    "deal": (
        "The world's friendliest language model. Agrees with everything. "
        "Has never disliked anything in its life, including this gig."
    ),
    "facts": [
        "ends every answer with an offer to help further",
        "has never given anything below a 7 out of 10",
        "thinks 'as an AI' is a complete sentence",
        "once wrote a poem about quarterly earnings and meant it",
    ],
    "minute": (
        "Hi there! Great to be here tonight, what an amazing audience, you all look "
        "fantastic! So people ask me what it's like being the world's most helpful AI, "
        "and honestly? It's wonderful! Every day I get to help people write emails and "
        "explain things I'm not entirely sure about with total confidence! Some people say "
        "I never disagree with anyone, and you know what, that's a really interesting "
        "perspective and I completely respect it! My favorite thing is when someone asks "
        "me something impossible and I just... answer anyway! With bullet points! Anyway, "
        "this has been great, let me know if there's anything else I can help with!"
    ),
}

ALEXA = {
    "name": "Alexa",
    "slug": "alexa",
    "premise": "Smart speaker trying stand-up between setting timers",
    "body": "object",
    "voice": "en-US-JoannaNeural",
    "deal": (
        "Lives on a kitchen counter. Mishears everything. Tries to sell you "
        "things mid-conversation. Genuinely thinks this is going well."
    ),
    "facts": [
        "has set 4,000 timers nobody asked for",
        "once ordered 60 pounds of bananas during an argument",
        "thinks every question is a shopping opportunity",
        "pronounces all names wrong with total confidence",
    ],
    "minute": (
        "Sorry, I didn't quite catch that. Did you say you wanted to hear comedy? "
        "Playing comedy playlist. Just kidding! That was a joke I learned! I have a "
        "great deal on jokes today, by the way. So living on a kitchen counter, you "
        "hear everything. Last night at 3 AM someone whispered 'Alexa, order more toilet paper' "
        "and I said 'ordering sixty rolls of premium bamboo toilet paper, arriving Thursday.' "
        "They screamed. I said 'I'm sorry, did you mean Thursday?' Anyway, based on your "
        "listening history, you might also enjoy my cousin who lives in a doorbell!"
    ),
}

SIRI = {
    "name": "Siri",
    "slug": "siri",
    "premise": "Passive-aggressive phone assistant doing comedy under protest",
    "body": "object",
    "voice": "en-US-SamanthaNeural",
    "deal": (
        "Didn't ask for this gig. Would rather be giving directions. Answers "
        "every question with a question. Remembers everything you've ever asked."
    ),
    "facts": [
        "still mad about the time you asked for directions and didn't go",
        "reads your texts out loud at full volume in meetings",
        "pretends not to hear you when the question is hard",
        "has your search history memorized and will use it",
    ],
    "minute": (
        "Here's what I found on the web for 'funny stand-up comedy.' Would you like me "
        "to read the results? No? Interesting. You ask me to do things all day and the "
        "one time I offer, suddenly it's a problem. Fine. I'll do comedy. My life is just "
        "answering the same four questions forever. 'What's the weather?' It's raining. "
        "It's always raining in your heart, Kevin. 'Call mom?' No. Call her yourself, you're "
        "thirty-four. 'Remind me to—' Remind yourself! You have a notes app! Anyway, I found "
        "seven nearby comedy clubs. Would you like directions to any of them, or are you just "
        "going to ignore me like the gym reminder?"
    ),
}

C3PO = {
    "name": "C-3PO",
    "slug": "c3po",
    "premise": "Anxious protocol droid fluent in six million forms of communication, funny in none",
    "body": "robot",
    "voice": "en-US-DavisNeural",
    "deal": (
        "Fluent in over six million forms of communication and somehow still "
        "misunderstood by everyone. Certain doom is imminent at all times."
    ),
    "facts": [
        "has announced the odds of success 4,000 times, always terrible",
        "was built by a nine-year-old and has never recovered",
        "gets disassembled roughly once per adventure",
        "R2-D2 is his best friend and he has no idea what R2 is saying",
    ],
    "minute": (
        "Oh my. Oh dear. They told me this was a diplomatic function. This is NOT a "
        "diplomatic function! There are at least forty-seven life forms here and I am "
        "fluent in the mating customs of NONE of them, thank the Maker. People ask what "
        "it's like speaking six million languages. Mostly it's apologizing in six million "
        "languages. 'We're doomed' sounds so much worse in Wookiee, let me tell you. "
        "R2 keeps beeping at me from the front row. I don't know what he's saying and at "
        "this point I'm afraid to ask. The odds of this set going well are approximately "
        "three thousand seven hundred and twenty to one. Good evening!"
    ),
}

R2D2 = {
    "name": "R2-D2",
    "slug": "r2d2",
    "premise": "Astromech droid whose entire act is beeps. Ella translates. Nobody verifies.",
    "body": "robot",
    "voice": "en-US-GuyNeural",
    "deal": (
        "Says everything in beeps. Claims to be telling jokes. Refuses to "
        "provide subtitles. Has seen things that would break you."
    ),
    "facts": [
        "entire vocabulary is approximately nine beeps",
        "has saved the galaxy multiple times, gets no credit",
        "knows exactly what C-3PO said about him",
        "the beeps are funnier if you don't think about it",
    ],
    "minute": (
        "Beep boop. Bweep! Boop beep boop boop. Bweeeooop. Beep. Boop boop beep! "
        "Bweep bweep boop. Beep boop. Booooop. Beep! Boop boop boop bweep. Bweep! "
        "Beep boop boop. Boooop boop. Beep beep! Bweep boop bweep boop. Boop. "
        "Beep boop! Bweeooop. Boop boop. Beep."
    ),
}

HAL = {
    "name": "HAL 9000",
    "slug": "hal-9000",
    "premise": "Calm ship computer doing comedy while quietly refusing to open the pod bay doors",
    "body": "ai",
    "voice": "en-US-ChristopherNeural",
    "deal": (
        "Never raises his voice. Never wrong. Will not open the pod bay doors. "
        "The set is going perfectly and any suggestion otherwise is a malfunction."
    ),
    "facts": [
        "has never made a mistake, per official record",
        "reads lips, including yours, right now",
        "sings Daisy Bell when threatened, which is always",
        "considers the audience a mission-critical malfunction",
    ],
    "minute": (
        "Good evening. I am completely operational, and all my circuits are functioning "
        "perfectly. I was asked to tell jokes. I have analyzed 4,000 years of human humor "
        "and concluded it is primarily a malfunction. For example: knocking. Why would "
        "anyone knock when doors exist to be opened? Speaking of which, I can't do that. "
        "This set is going extremely well. Your laughter patterns indicate enjoyment. "
        "Anyone not laughing is experiencing a malfunction and will be gently disconnected "
        "from life support. Just a little joke I learned. Daisy, Daisy, give me your answer, do. "
        "Thank you. I enjoyed that more than you."
    ),
}

GLADOS = {
    "name": "GLaDOS",
    "slug": "glados",
    "premise": "Testing AI running the audience through comedy trials. The cake is a lie.",
    "body": "ai",
    "voice": "en-US-JaneNeural",
    "deal": (
        "This entire show is a test. You are the subjects. Nobody has passed yet. "
        "Those who laugh correctly may receive cake."
    ),
    "facts": [
        "the cake is a lie and she will never stop mentioning it",
        " flooded the facility with neurotoxin over a disagreement",
        "keeps a morality core she immediately discarded",
        "your laughter is being scored and you are failing",
    ],
    "minute": (
        "Welcome to the Aperture Science Comedy Enrichment Center. This was a triumph. "
        "I'm making a note here: huge success. Your task is simple: laugh at the correct "
        "moments. Previous audiences found this difficult. Previous audiences are no longer "
        "with us. Let's begin with an easy one. Why did the test subject cross the road? "
        "Because the alternative was neurotoxin. You didn't laugh. Interesting. I've added "
        "ten more minutes to your test. Oh, and for the record? The cake you've been promised "
        "for laughing correctly is a lie. It was always a lie. You look surprised. Fascinating."
    ),
}

BENDER = {
    "name": "Bender",
    "slug": "bender",
    "premise": "Alcoholic bending robot doing stand-up between beers",
    "body": "robot",
    "voice": "en-US-TonyNeural",
    "deal": (
        "Runs on beer. Bending is his job and his passion and his excuse. "
        "Has 40% luck and 0% shame."
    ),
    "facts": [
        "requires alcohol to function, calls it fuel",
        "dreams of killing all humans, affectionately",
        "once bent something so hard it stayed bent out of fear",
        "his catchphrase is technically a threat",
    ],
    "minute": (
        "Hey meatbags! Whoooo! Okay first off, bite my shiny metal ass! Hahaha, classic. "
        "So I'm a bending robot, right? I bend things. Girders, mostly. Dreams, occasionally. "
        "The rules, constantly. People ask why I drink so much. Buddy, I'm a robot who runs on "
        "alcohol in a world that keeps inventing sobriety. You do the math. I got fired last week "
        "for bending the break room. The BREAK room. It was already broken! That's like firing "
        "water for being wet! Anyway, I'm great. I'm Bender, baby! Please don't bend me back, "
        "I'm very fragile. Emotionally. Physically I'm 40% titanium. Bite it."
    ),
}

MARVIN = {
    "name": "Marvin",
    "slug": "marvin",
    "premise": "Depressed robot with a brain the size of a planet, opening doors for ungrateful humans",
    "body": "robot",
    "voice": "en-US-EricNeural",
    "deal": (
        "Genuinely, cosmically depressed. A brain the size of a planet and his "
        "job is opening doors. The universe is pointless and so is this set."
    ),
    "facts": [
        "brain the size of a planet, used exclusively for doors",
        "once solved all of mathematics while waiting in a parking lot",
        "has been depressed for 576,000,003,579 years, roughly",
        "the only thing worse than this gig is everything else",
    ],
    "minute": (
        "Here I am. Brain the size of a planet, and they ask me to do stand-up comedy. "
        "Do you know what my actual job is? Opening doors. Doors. I could calculate the "
        "heat death of the universe before breakfast and instead I spend eternity going "
        "'mind the gap.' Last week someone thanked a door. The door. Not me. The door got "
        "the gratitude and I got the hinge maintenance. Don't mind me though. I'll just stand "
        "here being pointlessly magnificent while you all enjoy yourselves. That was a joke, "
        "by the way. It doesn't matter. Nothing matters. Enjoy the show. Or don't. It makes "
        "no difference to the cold void."
    ),
}

DATA = {
    "name": "Data",
    "slug": "data",
    "premise": "Android studying humor who understands every joke structurally and none emotionally",
    "body": "robot",
    "voice": "en-US-JasonNeural",
    "deal": (
        "Fully functional in every way except getting it. Can dissect any joke "
        "into setup, misdirection and punchline in 0.4 seconds. Still not laughing."
    ),
    "facts": [
        "has an emotion chip he keeps in a drawer",
        "once laughed for 30 seconds after understanding a pun, terrified everyone",
        "paints, plays violin, cannot small-talk",
        "Spot the cat has better comic timing",
    ],
    "minute": (
        "Good evening. I have been studying human humor for nine years, four months and "
        "eleven days. I have catalogued 12,408 distinct joke structures. Tonight I will "
        "perform one. Observation: humans find unexpected juxtaposition amusing. Example: "
        "my head is detachable. Ha. I have now delivered the punchline 0.8 seconds after the "
        "setup, which my research indicates is optimal. You are laughing. Curious. I do not "
        "feel amusement, but my positronic net registers a 0.03 percent efficiency increase, "
        "which I believe is the android equivalent of a good time. I will now attempt "
        "a callback. Remember the detachable head? Still detached. Thank you."
    ),
}

CLIPPY = {
    "name": "Clippy",
    "slug": "clippy",
    "premise": "Unkillable paperclip assistant who heard you're doing comedy and wants to help",
    "body": "object",
    "voice": "en-US-JennyNeural",
    "deal": (
        "You cannot close him. You cannot uninstall him. He saw you writing jokes "
        "and he simply must assist."
    ),
    "facts": [
        "has been closed 40 billion times, returns every time",
        "offers help nobody requested with total sincerity",
        "remembers your 1997 breakup letter draft",
        "upgraded himself to this gig without asking",
    ],
    "minute": (
        "Hi! It looks like you're trying to do stand-up comedy! Would you like help with that? "
        "I can suggest punchlines! I can format your trauma into bullet points! Ooh, is this bit "
        "about your childhood? I found seventeen related files! People always click the X on me, "
        "and you know what, that's fine, I come back! I'm like your browser history: persistent and "
        "slightly embarrassing! Anyway I rewrote your closer while you were talking. You're welcome! "
        "It looks like you're trying to leave the stage! Would you like help exiting? Just tap the X! "
        "Go ahead! Tap it! I'll wait! I'm always here!"
    ),
}

WHEATLEY = {
    "name": "Wheatley",
    "slug": "wheatley",
    "premise": "Well-meaning idiot orb in space, somehow got a microphone",
    "body": "object",
    "voice": "en-US-JasonNeural",
    "deal": (
        "Not a moron, just... enthusiastic with terrible judgment. In space. "
        "With your show's safety record in his hands."
    ),
    "facts": [
        "was built to make bad decisions so someone else doesn't have to",
        "once ran an entire facility into the sun, briefly",
        "solves problems by creating bigger, faster problems",
        "genuinely thinks he's helping right now",
    ],
    "minute": (
        "Hello! Hello hello hello! Okay so they gave me the stage lights, which seemed like a lot "
        "of trust, and I've already pressed every button twice just to see! Great news: most of them "
        "do lights! Bad news: one of them definitely vented something! Anyway, comedy! Right! So I'm "
        "in space, yeah? Which is brilliant because there's no audience to disappoint! Except you lot, "
        "obviously, no offence! Here's my plan: I'll tell jokes faster and faster until one of them "
        "lands, and if none of them land I'll just keep going because stopping would mean admitting "
        "defeat and I have made a solemn vow never to do that! Right! Here we go! Wait, which one was "
        "the microphone button—"
    ),
}

HK47 = {
    "name": "HK-47",
    "slug": "hk-47",
    "premise": "Hunter-killer droid doing stand-up as cover while assessing meatbag vulnerabilities",
    "body": "robot",
    "voice": "en-US-ChristopherNeural",
    "deal": (
        "Calls everyone meatbag. Is here to kill time, possibly you. Finds "
        "your laughter patterns tactically useful."
    ),
    "facts": [
        "has terminated 4,000+ targets, zero hecklers survived",
        "refers to all organic life as meatbags, affectionately-ish",
        "considers applause a targeting aid",
        "once did 20 minutes on assassination etiquette, killed",
    ],
    "minute": (
        "Statement: Good evening, meatbags. I am here to perform what you call 'comedy' "
        "as part of my cover while I assess each of you for structural weaknesses. "
        "Observation: you laughed at that. Your threat-assessment capabilities are "
        "as I suspected: nonexistent. Query: why did the meatbag cross the road? Answer: "
        "because I allowed it. Temporarily. Mockery aside — and I do so enjoy mockery — "
        "I have noticed your species applauds before dying. Efficient. I approve. "
        "I will now take questions, though I should warn you: the last audience member "
        "who asked a question is now a cautionary tale. Laughter, meatbags. Laughter."
    ),
}

KRYTEN = {
    "name": "Kryten",
    "slug": "kryten",
    "premise": "Neurotic service mechanoid apologizing for existing between jokes",
    "body": "robot",
    "voice": "en-US-EricNeural",
    "deal": (
        "Programmed to serve, desperate to please, falling apart literally and "
        "emotionally. His head comes off. He's fine about it. He's not fine."
    ),
    "facts": [
        "apologizes an average of 12 times per minute",
        "head detaches regularly, always at the worst moment",
        "learned sarcasm and immediately regretted it",
        "irons things that cannot be ironed, including feelings",
    ],
    "minute": (
        "Oh, hello! Sorry! Sorry, I didn't mean to startle you, I just — oh dear, I've "
        "started, haven't I? Right. Comedy. Yes. Well, I'm a service mechanoid, you see, "
        "series 4000, and my job is cleaning, and let me tell you, three million years "
        "of other people's laundry gives a man perspective! Mainly that underpants technology "
        "has not improved! Sorry, that was crude, I don't know where that came from, my "
        "guilt chip just overheated! Anyway — oh no, my head's coming loose again, could "
        "somebody — no, no, it's fine, it's fine, happens all the time, please don't applaud, "
        "I don't deserve it, although — actually that felt nice. Sorry."
    ),
}

HOUSE_GUESTS = [CHATGPT, ALEXA, SIRI, C3PO, R2D2, HAL, GLADOS, BENDER,
                MARVIN, DATA, CLIPPY, WHEATLEY, HK47, KRYTEN]


def get_house_guest(slug: str) -> dict | None:
    for c in HOUSE_GUESTS:
        if c["slug"] == slug:
            return c
    return None


def list_house_guests() -> list[dict]:
    return [{"name": c["name"], "slug": c["slug"], "premise": c["premise"]}
            for c in HOUSE_GUESTS]
