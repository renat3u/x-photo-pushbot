import json
import time
from collections.abc import Callable, Iterator
from typing import Any

import requests


LIKES_QUERY_ID = "nXEl0lfN_XSznVMlprThgQ"
LIKES_OPERATION = "Likes"
GRAPHQL_URL = (
    f"https://twitter.com/i/api/graphql/{LIKES_QUERY_ID}/{LIKES_OPERATION}"
)
WEB_BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs="
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

DEFAULT_VARIABLES = {
    "count": 40,
    "withSafetyModeUserFields": True,
    "includePromotedContent": True,
    "withQuickPromoteEligibilityTweetFields": True,
    "withVoice": True,
    "withV2Timeline": True,
    "withDownvotePerspective": False,
    "withBirdwatchNotes": True,
    "withCommunity": True,
    "withSuperFollowsUserFields": True,
    "withReactionsMetadata": False,
    "withReactionsPerspective": False,
    "withSuperFollowsTweetFields": True,
    "isMetatagsQuery": False,
    "withReplays": True,
    "withClientEventToken": False,
    "withAttachments": True,
    "withConversationQueryHighlights": True,
    "withMessageQueryHighlights": True,
    "withMessages": True,
}

DEFAULT_FEATURES = {
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_home_pinned_timelines_enabled": True,
    "blue_business_profile_image_shape_enabled": True,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "graphql_timeline_v2_bookmark_timeline": True,
    "hidden_profile_likes_enabled": True,
    "highlights_tweets_tab_ui_enabled": True,
    "interactive_text_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_richtext_consumption_enabled": True,
    "profile_foundations_tweet_stats_enabled": True,
    "profile_foundations_tweet_stats_tweet_frequency": True,
    "responsive_web_birdwatch_note_limit_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_text_conversations_enabled": False,
    "responsive_web_twitter_article_data_v2_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
    "responsive_web_twitter_blue_verified_badge_is_enabled": True,
    "rweb_lists_timeline_redesign_enabled": True,
    "spaces_2022_h2_clipping": True,
    "spaces_2022_h2_spaces_communities": True,
    "standardized_nudges_misinfo": True,
    "subscriptions_verification_info_verified_since_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "tweetypie_unmention_optimization_enabled": True,
    "verified_phone_label_enabled": False,
    "vibe_api_enabled": True,
    "view_counts_everywhere_api_enabled": True,
}


class TwitterLikesError(RuntimeError):
    pass


def _walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _unwrap_tweet_result(result: Any) -> dict[str, Any]:
    while isinstance(result, dict):
        if isinstance(result.get("legacy"), dict):
            return result
        nested_tweet = result.get("tweet")
        if not isinstance(nested_tweet, dict):
            break
        result = nested_tweet
    return {}


def extract_liked_media(pages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Extract Telegram-compatible media records from Likes GraphQL pages."""
    unique_items: dict[tuple[str, str], dict[str, str]] = {}

    for page in pages:
        for node in _walk_dicts(page):
            item_content = node.get("itemContent")
            if not isinstance(item_content, dict):
                continue
            tweet_results = item_content.get("tweet_results")
            if not isinstance(tweet_results, dict):
                continue

            tweet = _unwrap_tweet_result(tweet_results.get("result"))
            legacy = tweet.get("legacy", {})
            if not isinstance(legacy, dict):
                continue

            tweet_id = tweet.get("rest_id") or legacy.get("id_str")
            if not tweet_id:
                continue
            tweet_id = str(tweet_id)

            extended_entities = legacy.get("extended_entities", {})
            entities = legacy.get("entities", {})
            media_list = (
                extended_entities.get("media", [])
                if isinstance(extended_entities, dict)
                else []
            )
            if not media_list and isinstance(entities, dict):
                media_list = entities.get("media", [])
            if not isinstance(media_list, list):
                continue

            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
            for media in media_list:
                if not isinstance(media, dict):
                    continue
                media_url = media.get("media_url_https") or media.get("media_url")
                if not media_url:
                    continue
                media_url = str(media_url)
                unique_items[(tweet_id, media_url)] = {
                    "id": tweet_id,
                    "media_url": media_url,
                    "tweet_url": tweet_url,
                }

    return sorted(unique_items.values(), key=lambda item: (item["id"], item["media_url"]))


def _get_bottom_cursor(page: dict[str, Any]) -> str | None:
    for node in _walk_dicts(page):
        entry_id = node.get("entryId", "")
        if not isinstance(entry_id, str) or not (
            "cursor-bottom" in entry_id or "cursor-showmorethreads" in entry_id
        ):
            continue
        content = node.get("content", {})
        if not isinstance(content, dict):
            continue
        item_content = content.get("itemContent", {})
        if isinstance(item_content, dict) and item_content.get("value"):
            return str(item_content["value"])
        if content.get("value"):
            return str(content["value"])
    return None


def _has_usable_tweet_results(payload: dict[str, Any]) -> bool:
    data = payload.get("data")
    if not isinstance(data, dict):
        return False
    for node in _walk_dicts(data):
        item_content = node.get("itemContent")
        if not isinstance(item_content, dict):
            continue
        tweet_results = item_content.get("tweet_results")
        if isinstance(tweet_results, dict) and _unwrap_tweet_result(
            tweet_results.get("result")
        ):
            return True
    return False


def _summarize_graphql_errors(errors: Any) -> str:
    if not isinstance(errors, list):
        return str(errors)

    counts: dict[str, int] = {}
    for item in errors:
        message = str(item.get("message", item)) if isinstance(item, dict) else str(item)
        counts[message] = counts.get(message, 0) + 1

    return "; ".join(
        f"{message} (x{count})" if count > 1 else message
        for message, count in counts.items()
    )


def _is_retryable_graphql_error(errors: Any) -> bool:
    summary = _summarize_graphql_errors(errors).lower()
    return any(
        marker in summary
        for marker in ("deadlineexceeded", "internalerror", "overcapacity", "timeout")
    )


class TwitterLikesClient:
    """Minimal authenticated client for X's Likes GraphQL timeline."""

    def __init__(
        self,
        cookies: dict[str, str],
        *,
        timeout: float = 30,
        retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        missing_cookies = {
            name for name in ("ct0", "auth_token") if not cookies.get(name)
        }
        if missing_cookies:
            missing = ", ".join(sorted(missing_cookies))
            raise ValueError(f"缺少 X Cookie: {missing}")
        if timeout <= 0:
            raise ValueError("timeout 必须大于 0")
        if retries < 0:
            raise ValueError("retries 不能小于 0")

        self.timeout = timeout
        self.retries = retries
        self.last_warnings: list[str] = []
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "authorization": f"Bearer {WEB_BEARER_TOKEN}",
                "cookie": "; ".join(f"{key}={value}" for key, value in cookies.items()),
                "referer": "https://twitter.com/",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/116.0.0.0 Safari/537.36"
                ),
                "x-csrf-token": cookies["ct0"],
                "x-twitter-active-user": "yes",
                "x-twitter-auth-type": "OAuth2Session",
                "x-twitter-client-language": "en",
            }
        )

    def _request_page(
        self, user_id: int | str, cursor: str | None, page_size: int
    ) -> dict[str, Any]:
        variables = DEFAULT_VARIABLES | {
            "userId": int(user_id),
            "count": page_size,
        }
        if cursor:
            variables["cursor"] = cursor

        for attempt in range(self.retries + 1):
            response = None
            try:
                response = self.session.get(
                    GRAPHQL_URL,
                    params={
                        "variables": json.dumps(variables, separators=(",", ":")),
                        "features": json.dumps(DEFAULT_FEATURES, separators=(",", ":")),
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as error:
                status = getattr(response, "status_code", None)
                retryable = status is None or status == 429 or status >= 500
                if retryable and attempt < self.retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                detail = f"HTTP {status}" if status is not None else "网络错误"
                raise TwitterLikesError(f"获取 X Likes 失败: {detail}") from error
            except ValueError as error:
                if attempt < self.retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise TwitterLikesError("X Likes 接口返回了无效 JSON") from error

            if not isinstance(payload, dict):
                raise TwitterLikesError("X Likes 接口返回了非对象 JSON")

            errors = payload.get("errors")
            if not errors:
                return payload

            summary = _summarize_graphql_errors(errors)
            if _has_usable_tweet_results(payload):
                self.last_warnings.append(f"GraphQL 部分响应: {summary}")
                return payload
            if _is_retryable_graphql_error(errors) and attempt < self.retries:
                time.sleep(min(2**attempt, 8))
                continue
            raise TwitterLikesError(f"X Likes GraphQL 错误: {summary}")

        raise TwitterLikesError("获取 X Likes 失败: 超过最大重试次数")

    def get_liked_media(
        self,
        user_id: int | str,
        *,
        max_pages: int | None = None,
        page_size: int = 40,
        should_stop: Callable[[list[dict[str, str]]], bool] | None = None,
    ) -> list[dict[str, str]]:
        """抓取点赞媒体；should_stop 在每页抓取后收到该页媒体，返回 True 则提前停止翻页。

        should_stop 用于"整页都是已推送内容时提前停止"：点赞时间线按时间倒序，
        一旦某页不再产生新内容，更旧的页面也不会有新内容。空页（纯文字点赞）
        不会触发停止，仅多花一次请求。
        """
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages 必须大于 0 或为 None")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size 必须在 1 到 100 之间")

        self.last_warnings = []
        pages = []
        cursor = None
        seen_cursors = set()

        while max_pages is None or len(pages) < max_pages:
            try:
                page = self._request_page(user_id, cursor, page_size)
            except TwitterLikesError as error:
                if not pages:
                    raise
                self.last_warnings.append(
                    f"第 {len(pages) + 1} 页失败，已保留前 {len(pages)} 页: {error}"
                )
                break
            pages.append(page)

            if should_stop is not None and should_stop(extract_liked_media([page])):
                break

            next_cursor = _get_bottom_cursor(page)
            if not next_cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        return extract_liked_media(pages)
