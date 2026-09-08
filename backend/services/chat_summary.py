"""Chat Summary Engine — synthesizes chat into signals.

Not a conversation engine. Not an LLM response generator.
Just: chat → labels, nicknames, sentiment, highlight quotes.

Reference: anime.dm — chat features
"""

import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class ChatSummary:
    """Aggregated chat data for an act."""
    labels: list[str] = field(default_factory=list)       # ["depressed", "horny", "unqualified"]
    nicknames: list[str] = field(default_factory=list)    # ["The Ass Detective", "Officer No-Nose"]
    top_reactions: list[dict] = field(default_factory=list)  # [{"text": "poor dog", "count": 19}]
    sentiment: str = "neutral"                            # strong_positive, positive, neutral, negative, mixed
    sentiment_score: float = 0.5                          # 0-1
    total_messages: int = 0
    unique_chatters: int = 0
    highlight_quotes: list[str] = field(default_factory=list)  # best/funniest chat lines
    return_rate: float = 0.0


# ── Label Detection ─────────────────────────────────────────────────

# Adjective patterns that chat uses to describe characters
LABEL_PATTERNS = {
    r"\bdepressed\b": "depressed",
    r"\bsad\b": "sad",
    r"\bcute\b": "cute",
    r"\badorable\b": "cute",
    r"\bcreepy\b": "creepy",
    r"\bsus\b": "suspicious",
    r"\bfraud\b": "fraud",
    r"\bimpostor\b": "fraud",
    r"\blegend\b": "legend",
    r"\bgay\b": "gay",
    r"\bbroken\b": "broken",
    r"\bchaotic\b": "chaotic",
    r"\bbased\b": "based",
    r"\bcringe\b": "cringe",
    r"\bgoat\b": "GOAT",
    r"\bgoats?\b": "GOAT",
    r"\bgo off\b": "going off",
    r"\bcook\b": "cooking",
    r"\blet him cook\b": "cooking",
    r"\bpoor (guy|dog|soul|thing)\b": "sympathetic",
    r"\bneeds? (a )?lawyer\b": "needs lawyer",
    r"\bunhinged\b": "unhinged",
    r"\bbless\b": "blessed",
    r"\bf\b": "F in chat",
    r"\brip\b": "RIP",
    r"\bwtf\b": "wtf",
    r"\bbruh\b": "bruh",
    r"\bno (way|shot)\b": "disbelief",
    r"\bim dead\b": "dying laughing",
    r"\bimagine\b": "imaginative",
    r"\bpetition\b": "petition",
}

# Nickname patterns
NICKNAME_PATTERNS = [
    r"(?:call(?:ed|ing)?|named|nicknamed?|renamed?)\s+(?:him|her|it)\s+[\"']?(.+?)[\"']?\s*$",
    r"[\"'](.+?)[\"']",
    r"^(?:the|a|an)\s+\w+(?:\s+\w+){0,3}$",  # "The Ass Detective" etc.
]


class ChatSummaryEngine:
    """Synthesize chat messages into structured signals.

    Input: list of chat messages during a performance
    Output: ChatSummary with labels, nicknames, sentiment, quotes
    """

    def analyze(self, messages: list[str], return_votes: int = 0,
                total_viewers: int = 0) -> ChatSummary:
        """Analyze a batch of chat messages."""
        summary = ChatSummary()
        summary.total_messages = len(messages)
        summary.unique_chatters = len(set(messages))  # simplified

        if not messages:
            return summary

        # Extract labels
        label_counts = Counter()
        for msg in messages:
            msg_lower = msg.lower()
            for pattern, label in LABEL_PATTERNS.items():
                if re.search(pattern, msg_lower):
                    label_counts[label] += 1

        # Top labels (appeared 2+ times or >5% of messages)
        threshold = max(2, len(messages) * 0.05)
        summary.labels = [
            label for label, count in label_counts.most_common(10)
            if count >= threshold
        ]

        # Extract nicknames
        nick_counts = Counter()
        for msg in messages:
            for pattern in NICKNAME_PATTERNS:
                match = re.search(pattern, msg, re.IGNORECASE)
                if match:
                    nick = match.group(1) if match.lastindex else match.group(0)
                    nick = nick.strip().strip("\"'")
                    if 3 < len(nick) < 40 and nick[0].isupper():
                        nick_counts[nick] += 1

        summary.nicknames = [n for n, c in nick_counts.most_common(5) if c >= 2]

        # Top reactions (repeated phrases)
        phrase_counts = Counter()
        for msg in messages:
            msg_clean = msg.lower().strip()
            if 3 < len(msg_clean) < 50:
                phrase_counts[msg_clean] += 1

        summary.top_reactions = [
            {"text": phrase, "count": count}
            for phrase, count in phrase_counts.most_common(10)
            if count >= 2
        ]

        # Sentiment (simple keyword-based)
        positive = sum(1 for m in messages if any(w in m.lower() for w in [
            "love", "funny", "amazing", "goat", "legend", "cook", "based",
            "brilliant", "incredible", "hilarious", "perfect", "yes",
        ]))
        negative = sum(1 for m in messages if any(w in m.lower() for w in [
            "bad", "boring", "cringe", "skip", "next", "waste",
            "terrible", "awful", "unfunny", "try hard",
        ]))

        if positive + negative > 0:
            ratio = positive / (positive + negative)
            summary.sentiment_score = ratio
            if ratio > 0.7:
                summary.sentiment = "strong_positive"
            elif ratio > 0.55:
                summary.sentiment = "positive"
            elif ratio < 0.3:
                summary.sentiment = "negative"
            elif ratio < 0.45:
                summary.sentiment = "mixed"
            else:
                summary.sentiment = "neutral"

        # Highlight quotes (messages with high engagement potential)
        for msg in messages:
            if (len(msg) > 15 and len(msg) < 100 and
                any(w in msg.lower() for w in ["he ", "she ", "it ", "this ", "that "]) and
                not msg.startswith("@")):
                summary.highlight_quotes.append(msg)
                if len(summary.highlight_quotes) >= 5:
                    break

        # Return rate
        if total_viewers > 0:
            summary.return_rate = return_votes / total_viewers

        return summary

    def generate_review(self, summary: ChatSummary, character_name: str) -> str:
        """Generate a post-show audience review from chat summary.

        This is what the creator sees after their act.
        """
        lines = []
        lines.append(f"AUDIENCE REACTION — {character_name}")
        lines.append("")

        if summary.labels:
            lines.append(f"Chat thinks {character_name} is:")
            lines.append(f"  {' · '.join(summary.labels[:5])}")
            lines.append("")

        if summary.top_reactions:
            top = summary.top_reactions[0]
            lines.append(f'Biggest reaction: "{top["text"]}" × {top["count"]}')
            lines.append("")

        if summary.highlight_quotes:
            lines.append("Chat said:")
            for q in summary.highlight_quotes[:3]:
                lines.append(f"  • {q}")
            lines.append("")

        if summary.return_rate > 0:
            lines.append(f"Would return: {summary.return_rate:.0%}")

        return "\n".join(lines)


# Singleton
chat_summary_engine = ChatSummaryEngine()
