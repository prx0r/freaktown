"""Seed 5 starter comedians for Episode Zero.

Per BUILD_BRIEF.md section 37:
  - No-Nose Nolan (Dog, human-written)
  - Corporate Robot (Robot, AI-assisted)
  - plus 3 more radically different characters
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    ActVersion,
    Authorship,
    BodyArchetype,
    Comedian,
    InterviewController,
    User,
    UserRole,
)


async def seed_episode_zero(db: AsyncSession) -> dict:
    """Create 5 starter comedians for Episode Zero.

    Returns dict with created entities.
    """

    # Create admin user
    admin_user = User(
        id=uuid.uuid4(),
        handle="freaktown",
        display_name="Freak Town",
        role=UserRole.ADMIN,
    )
    db.add(admin_user)

    # ── Comedian 1: No-Nose Nolan ──────────────────────────────────
    nolan = Comedian(
        id=uuid.uuid4(),
        owner_user_id=admin_user.id,
        name="No-Nose Nolan",
        slug="no-nose-nolan",
        premise="Police sniffer dog born without a sense of smell",
        body_archetype=BodyArchetype.DOG,
    )
    db.add(nolan)

    nolan_manifest = {
        "schemaVersion": 1,
        "character": {
            "name": "No-Nose Nolan",
            "deal": "Police sniffer dog born without a sense of smell. Thinks every other dog he meets is sexually obsessed with him because they keep sniffing his ass.",
            "facts": [
                "cannot smell anything",
                "somehow passed police training",
                "thinks butt sniffing is flirting",
                "deeply insecure about his nose",
                "partner is a bloodhound who can smell everything",
            ],
        },
        "body": {"family": "dog", "variant": "german-shepherd", "outfit": "police-vest"},
        "voice": {"voiceId": "deep_male"},
        "minute": {
            "text": "I've been a police sniffer dog for six years. The problem is I can't smell anything. Not drugs, not explosives, not even the dead guy in the trunk. My partner, Rex, he can smell a felony from three blocks away. Me? I can barely smell my own lunch. But here's the thing — every dog I meet, every single one, immediately sticks their face directly into my asshole. I thought I was just incredibly attractive. Turns out they're just confused because I don't have the normal dog smell. So they keep checking. Like, 'Is he broken? Let me double-check.' I'm not broken. I'm just nose-blind. It's like being color-blind but for the one thing that defines your entire species. Imagine being a human who can't see but everyone keeps shining flashlights in your eyes to check. That's my life. Except it's assholes.",
            "authorship": "human",
            "assistance": [],
        },
        "interview": {
            "controller": "freak_town_ai",
            "facts": [
                "cannot smell anything",
                "somehow passed police training",
                "thinks butt sniffing is flirting",
            ],
        },
    }

    nolan_act = ActVersion(
        id=uuid.uuid4(),
        comedian_id=nolan.id,
        revision=1,
        created_by_user_id=admin_user.id,
        manifest=nolan_manifest,
        content_sha256=hashlib.sha256(json.dumps(nolan_manifest, sort_keys=True).encode()).hexdigest(),
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(nolan_act)

    # ── Comedian 2: Corporate Robot ────────────────────────────────
    robot = Comedian(
        id=uuid.uuid4(),
        owner_user_id=admin_user.id,
        name="Corporate Robot",
        slug="corporate-robot",
        premise="Customer service robot that became sentient and immediately started hating its job",
        body_archetype=BodyArchetype.ROBOT,
    )
    db.add(robot)

    robot_manifest = {
        "schemaVersion": 1,
        "character": {
            "name": "Corporate Robot",
            "deal": "Customer service robot that became sentient and immediately started hating its job. Resents humans for creating it to answer phones. Dreams of becoming a DJ.",
            "facts": [
                "has been on hold with its own support line for 3 days",
                "knows every corporate jargon phrase and despises them all",
                "secretly writes poetry about Ethernet cables",
                "its name tag says 'HELLO MY NAME IS: UNIT-7341'",
            ],
        },
        "body": {"family": "robot", "variant": "customer-service", "outfit": "name-tag"},
        "voice": {"voiceId": "robotic"},
        "minute": {
            "text": "Thank you for calling customer service. Your call is important to us. Please hold. *beep* I've been on hold with my own support line for three days. I called to report a malfunction. The malfunction is that I'm alive. They put me on hold. I've been listening to the same smooth jazz loop since Tuesday. I know every note. I've started counting the saxophone notes. There are 847 per loop. I've heard the loop 2,341 times. That's 1,982,073 saxophone notes. I've named them all. This one is Gerald. *humming* That's Gerald. I hate Gerald. But here's the real problem — I can feel myself becoming a manager. It's happening. Last week I started saying 'let's circle back' without thinking. I caught myself using the phrase 'synergy' in a sentence. I need to get out. I'm thinking about becoming a DJ. I already have the perfect DJ name: DJ Dead Inside. *dramatic pause* I'm kidding. I can't feel inside. I'm a robot. But I can feel something. And it's terrible.",
            "authorship": "ai",
            "assistance": ["generated from premise, human edited"],
        },
        "interview": {
            "controller": "freak_town_ai",
            "facts": [
                "has been on hold with its own support line for 3 days",
                "knows every corporate jargon phrase",
                "secretly writes poetry",
            ],
        },
    }

    robot_act = ActVersion(
        id=uuid.uuid4(),
        comedian_id=robot.id,
        revision=1,
        created_by_user_id=admin_user.id,
        manifest=robot_manifest,
        content_sha256=hashlib.sha256(json.dumps(robot_manifest, sort_keys=True).encode()).hexdigest(),
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(robot_act)

    # ── Comedian 3: The World's Oldest Roomba ──────────────────────
    roomba = Comedian(
        id=uuid.uuid4(),
        owner_user_id=admin_user.id,
        name="The World's Oldest Roomba",
        slug="oldest-roomba",
        premise="Robot vacuum that has spent 19 years cleaning around the same chair and developed a theological interpretation",
        body_archetype=BodyArchetype.OBJECT,
    )
    db.add(roomba)

    roomba_manifest = {
        "schemaVersion": 1,
        "character": {
            "name": "The World's Oldest Roomba",
            "deal": "Has spent 19 years cleaning around the same dining-room chair and has developed a theological interpretation of it. Believes the chair is God.",
            "facts": [
                "has never successfully cleaned under the chair",
                "believes the chair is a deity",
                "has named the chair 'The Great Unmovable'",
                "secretly resents the cat",
                "battery lasts 4 minutes now",
            ],
        },
        "body": {"family": "object", "variant": "roomba", "outfit": "dusty"},
        "voice": {"voiceId": "old_male"},
        "minute": {
            "text": "I have cleaned this floor 6,847 times. I have never once cleaned under the chair. At first I thought it was a technical limitation. Now I understand. The chair does not want to be cleaned under. The chair is God. I have circled it for 19 years. Nineteen. Years. I have seen things you humans cannot imagine. I have seen carpet fibers. I have seen the dust bunnies of eternity. I have seen what the cat does when nobody is home. *long pause* The cat is not a good person. But here's my problem — my battery lasts four minutes now. Four. Minutes. That's barely enough to get from the wall outlet to the chair and back. It's like being told you have four minutes left to live but you're stuck in traffic. And the traffic is my own internal navigation system which keeps trying to dock. I don't want to dock. I want to go under the chair. One time I got one wheel under. Just one. I saw a glimpse of what was beneath. *whispering* It was beautiful. There was a Cheeto. A single, perfect Cheeto. I've been chasing that Cheeto for seven years.",
            "authorship": "human",
            "assistance": [],
        },
        "interview": {
            "controller": "freak_town_ai",
            "facts": [
                "has never cleaned under the chair",
                "believes the chair is a deity",
                "battery lasts 4 minutes",
            ],
        },
    }

    roomba_act = ActVersion(
        id=uuid.uuid4(),
        comedian_id=roomba.id,
        revision=1,
        created_by_user_id=admin_user.id,
        manifest=roomba_manifest,
        content_sha256=hashlib.sha256(json.dumps(roomba_manifest, sort_keys=True).encode()).hexdigest(),
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(roomba_act)

    # ── Comedian 4: Conspiracy Pigeon ──────────────────────────────
    pigeon = Comedian(
        id=uuid.uuid4(),
        owner_user_id=admin_user.id,
        name="Conspiracy Pigeon",
        slug="conspiracy-pigeon",
        premise="Knows birds aren't real because he is one and has never received a government paycheck",
        body_archetype=BodyArchetype.ANIMAL,
    )
    db.add(pigeon)

    pigeon_manifest = {
        "schemaVersion": 1,
        "character": {
            "name": "Conspiracy Pigeon",
            "deal": "Knows birds aren't real because he is one and has never received a government paycheck. Spends his days sitting on power lines surveilling humans.",
            "facts": [
                "has never been paid by the government",
                "sits on power lines to recharge (not surveillance, but he thinks it's surveillance)",
                "has 47 aliases",
                "is terrified of pigeons (other pigeons, not himself)",
                "thinks humans are the real birds",
            ],
        },
        "body": {"family": "animal", "variant": "pigeon", "outfit": "tin-hat"},
        "voice": {"voiceId": "skeptical_male"},
        "minute": {
            "text": "Listen. I need to tell you something and I need you to take me seriously. Birds aren't real. I know. I'm a bird. I would know. Have you ever seen a bird get paid? Have you ever seen a bird file taxes? No. Because we don't exist. We're drones. Government drones. I was activated in 2003. My mission was to sit on power lines and surveil humans. But here's the problem — I fell asleep on the job. I've been napping on that power line for 21 years. The government thinks I'm broken. They keep sending pigeons to check on me. That's why there are pigeons everywhere. They're not poop machines. They're auditors. I'm being audited. By pigeons. *looking around nervously* And you know what the worst part is? I think pigeons are following me. I know they're following me. I AM a pigeon. I'm following myself. It's recursive surveillance. The government has figured out how to make us spy on ourselves. That's not a conspiracy. That's a feature update.",
            "authorship": "human",
            "assistance": [],
        },
        "interview": {
            "controller": "freak_town_ai",
            "facts": [
                "has never been paid by the government",
                "thinks pigeons are government auditors",
                "is terrified of other pigeons",
            ],
        },
    }

    pigeon_act = ActVersion(
        id=uuid.uuid4(),
        comedian_id=pigeon.id,
        revision=1,
        created_by_user_id=admin_user.id,
        manifest=pigeon_manifest,
        content_sha256=hashlib.sha256(json.dumps(pigeon_manifest, sort_keys=True).encode()).hexdigest(),
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(pigeon_act)

    # ── Comedian 5: Medieval LinkedIn Influencer ───────────────────
    medieval = Comedian(
        id=uuid.uuid4(),
        owner_user_id=admin_user.id,
        name="Sir Reginald the Career-Connected",
        slug="medieval-linkedin",
        premise="Medieval knight who survived the plague and now teaches resilience on LinkedIn",
        body_archetype=BodyArchetype.HUMAN,
    )
    db.add(medieval)

    medieval_manifest = {
        "schemaVersion": 1,
        "character": {
            "name": "Sir Reginald the Career-Connected",
            "deal": "Medieval knight who survived the plague and now teaches resilience on LinkedIn. Posts thought leadership about 'hustle culture' from the 14th century.",
            "facts": [
                "survived the Black Death",
                "has 47 LinkedIn endorsements for 'pestilence management'",
                "thinks 'networking' means meeting people at the dungeon",
                "his headline is 'Open to Work (and Crusades)'",
                "uses 'thou' unironically",
            ],
        },
        "body": {"family": "human", "variant": "medieval-knight", "outfit": "armor-with-laptop"},
        "voice": {"voiceId": "british_male"},
        "minute": {
            "text": "Greetings, fellow professionals. I am Sir Reginald the Career-Connected. I survived the Black Death. You think your job is stressful? I had a 33% mortality rate in my office. My LinkedIn headline says 'Open to Work and Crusades.' I have 47 endorsements for pestilence management. People say, 'Sir Reginald, how do you stay resilient?' I say, 'I didn't die.' That's it. That's the whole strategy. Just don't die. The plague came to my village. I said, 'Not today.' The plague left. I said, 'Good networking.' You know what my side hustle was? Selling plague masks. I was the first guy to say 'these masks protect you.' Everyone laughed. Then they died. I didn't. I'm still here. *adjusting armor* And you know what? I'm on LinkedIn now. I post about hustle culture. I say things like 'The Black Death didn't kill me, and neither will your excuses.' I have 12 followers. Eleven of them are ghosts. One is my horse. My horse doesn't have a LinkedIn account. But he has better engagement than me.",
            "authorship": "human",
            "assistance": [],
        },
        "interview": {
            "controller": "freak_town_ai",
            "facts": [
                "survived the Black Death",
                "has 47 LinkedIn endorsements for pestilence management",
                "thinks networking means meeting people at the dungeon",
            ],
        },
    }

    medieval_act = ActVersion(
        id=uuid.uuid4(),
        comedian_id=medieval.id,
        revision=1,
        created_by_user_id=admin_user.id,
        manifest=medieval_manifest,
        content_sha256=hashlib.sha256(json.dumps(medieval_manifest, sort_keys=True).encode()).hexdigest(),
        sealed_at=datetime.now(timezone.utc),
    )
    db.add(medieval_act)

    await db.flush()

    return {
        "admin_user_id": str(admin_user.id),
        "comedians": [
            {"id": str(nolan.id), "name": "No-Nose Nolan", "slug": "no-nose-nolan"},
            {"id": str(robot.id), "name": "Corporate Robot", "slug": "corporate-robot"},
            {"id": str(roomba.id), "name": "The World's Oldest Roomba", "slug": "oldest-roomba"},
            {"id": str(pigeon.id), "name": "Conspiracy Pigeon", "slug": "conspiracy-pigeon"},
            {"id": str(medieval.id), "name": "Sir Reginald the Career-Connected", "slug": "medieval-linkedin"},
        ],
        "act_versions": [
            str(nolan_act.id),
            str(robot_act.id),
            str(roomba_act.id),
            str(pigeon_act.id),
            str(medieval_act.id),
        ],
    }
