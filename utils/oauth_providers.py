from abc import ABC, abstractmethod
from typing import Any

from utils.oauth_utils import (
    extract_user_info_from_discord,
    extract_user_info_from_github,
    extract_user_info_from_google,
)


class OAuthProviderStrategy(ABC):
    """Encapsulates everything that differs between OAuth providers.

    The only provider-specific concern is how to exchange a token for a
    normalised user-info dict.  Everything else (state verification, the
    link/login/register flow, token generation, redirects) is handled once
    in the generic callback handler.
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """Provider key used in URLs and the database (e.g. 'google')."""
        ...

    @abstractmethod
    def fetch_user_info(self, client: Any, token: Any) -> dict[str, Any]:
        """Fetch and normalise user info from the provider.

        Args:
            client: Authlib OAuth remote app for this provider.
            token:  Token dict returned by ``authorize_access_token()``.

        Returns:
            Standardised user-info dict with at minimum:
            ``provider_user_id``, ``email``, ``email_verified``, ``name``, ``picture``.
        """
        ...


class GoogleStrategy(OAuthProviderStrategy):
    key = "google"

    def fetch_user_info(self, client: Any, token: Any) -> dict[str, Any]:
        # Google includes userinfo in the token when openid scope is used;
        # fall back to an explicit API call if it is absent.
        userinfo = token.get("userinfo")
        if userinfo is None:
            userinfo = client.get("userinfo", token=token).json()
        return extract_user_info_from_google(userinfo)


class GitHubStrategy(OAuthProviderStrategy):
    key = "github"

    def fetch_user_info(self, client: Any, token: Any) -> dict[str, Any]:
        # GitHub requires a separate call to get verified email addresses.
        user = client.get("user", token=token).json()
        emails_response = client.get("user/emails", token=token)
        emails = emails_response.json() if emails_response.status_code == 200 else []
        if not isinstance(emails, list):
            emails = []
        return extract_user_info_from_github(user, emails)


class DiscordStrategy(OAuthProviderStrategy):
    key = "discord"

    def fetch_user_info(self, client: Any, token: Any) -> dict[str, Any]:
        user = client.get("users/@me", token=token).json()
        return extract_user_info_from_discord(user)


# Registry: maps provider key → strategy instance.
# To add a new provider: create a subclass above, then add it here.
PROVIDER_STRATEGIES: dict[str, OAuthProviderStrategy] = {
    s.key: s() for s in [GoogleStrategy, GitHubStrategy, DiscordStrategy]
}
