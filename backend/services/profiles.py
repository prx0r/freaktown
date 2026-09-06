"""Character pages and creator profiles.

Per vision.md:
  - Character page: avatar, earnings, appearances, best laugh, followers, acts
  - Creator profile: all characters created
  - Follow/tip actions
"""

from dataclasses import dataclass, field


@dataclass
class CharacterPage:
    """Public character page data."""
    id: str
    name: str
    slug: str
    premise: str
    body_archetype: str
    creator_handle: str
    creator_display_name: str
    total_earned_usdc: float = 0.0
    appearances: int = 0
    best_laugh_share: float = 0.0
    followers: int = 0
    acts: list[dict] = field(default_factory=list)
    is_followed: bool = False


@dataclass
class CreatorProfile:
    """Public creator profile data."""
    id: str
    handle: str
    display_name: str
    created_at: str
    characters: list[dict] = field(default_factory=list)
    total_earnings_usdc: float = 0.0
    total_appearances: int = 0
    follower_count: int = 0


class ProfileService:
    """Generates character pages and creator profiles."""

    async def get_character_page(
        self,
        slug: str,
        viewer_user_id: str | None = None,
        db=None,
    ) -> CharacterPage | None:
        """Get a character's public page."""
        # In production, query from DB
        return None

    async def get_creator_profile(
        self,
        handle: str,
        viewer_user_id: str | None = None,
        db=None,
    ) -> CreatorProfile | None:
        """Get a creator's public profile."""
        # In production, query from DB
        return None

    async def follow_character(
        self,
        user_id: str,
        comedian_id: str,
        db=None,
    ) -> dict:
        """Follow a character."""
        return {"status": "followed", "comedian_id": comedian_id}

    async def unfollow_character(
        self,
        user_id: str,
        comedian_id: str,
        db=None,
    ) -> dict:
        """Unfollow a character."""
        return {"status": "unfollowed", "comedian_id": comedian_id}

    async def get_character_followers(
        self,
        comedian_id: str,
        limit: int = 50,
        db=None,
    ) -> list[dict]:
        """Get followers of a character."""
        return []

    async def get_creator_characters(
        self,
        user_id: str,
        db=None,
    ) -> list[dict]:
        """Get all characters created by a user."""
        return []


# Singleton
profile_service = ProfileService()
