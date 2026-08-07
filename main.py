import hashlib
import itertools
import json
import logging
import logging.handlers
import os
import time

import requests

from twitter_likes import TwitterLikesClient


userid = 114514
bottoken = "114514:ACBD"
chatid = "-114514"
sleeptime = 86400
cookies = {
    "ct0": "114514",
    "auth_token": "114514",
}

max_like_pages = 5
like_page_size = 40

STATE_VERSION = 3
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "pre_results.json")

PUSH_BATCH_SIZE = 20
PUSH_BATCH_SLEEP = 30

TELEGRAM_ALBUM_MAX = 10

LOG_FILE = os.path.join(BASE_DIR, "main.log")
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 7

logger = logging.getLogger("main")

likes_client = TwitterLikesClient(cookies)


def hash_item(item):
    raw = f"{item['id']}|{item['media_url']}"
    return hashlib.md5(raw.encode()).hexdigest()


def normalize_items(items):
    unique_items = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        if not all(
            isinstance(item.get(field), str) and item[field]
            for field in ("id", "media_url", "tweet_url")
        ):
            continue
        item_hash = hash_item(item)
        unique_items[item_hash] = item
    return sorted(unique_items.values(), key=lambda x: (x["id"], x["media_url"]))


def setup_logging():
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def load_saved_data(file_path):
    default_state = {
        "version": STATE_VERSION,
        "initialized": False,
        "pushed_hashes": [],
        "last_items": [],
    }

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            raw = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_state
    
    if isinstance(raw, list):
        items = normalize_items(raw)
        return {
            "version": STATE_VERSION,
            "initialized": bool(items),
            "pushed_hashes": sorted({hash_item(item) for item in items}),
            "last_items": items,
        }

    if isinstance(raw, dict):
        pushed_hashes = raw.get("pushed_hashes", [])
        last_items = raw.get("last_items", [])

        if not isinstance(pushed_hashes, list):
            pushed_hashes = []
        if not isinstance(last_items, list):
            last_items = []

        return {
            "version": STATE_VERSION,
            "initialized": bool(raw.get("initialized", pushed_hashes or last_items)),
            "pushed_hashes": sorted(
                {value for value in pushed_hashes if isinstance(value, str)}
            ),
            "last_items": normalize_items(last_items),
        }

    return default_state


def save_state(file_path, state):
    safe_state = {
        "version": STATE_VERSION,
        "initialized": bool(state.get("initialized", False)),
        "pushed_hashes": sorted(
            {
                value
                for value in state.get("pushed_hashes", [])
                if isinstance(value, str)
            }
        ),
        "last_items": normalize_items(state.get("last_items", [])),
    }
    temp_path = f"{file_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(safe_state, file, indent=4, ensure_ascii=False)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, file_path)


def get_differences(new_data, pushed_hashes):
    pushed_hashes_set = set(pushed_hashes)
    new_items = []
    for item in normalize_items(new_data):
        if hash_item(item) not in pushed_hashes_set:
            new_items.append(item)
    return new_items


def _send_photo(item):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bottoken}/sendPhoto",
            data={
                "chat_id": chatid,
                "caption": item["tweet_url"],
                "photo": item["media_url"],
            },
            timeout=(10, 30),
        )
        response_data = response.json()
        if (
            response.status_code == 200
            and isinstance(response_data, dict)
            and response_data.get("ok") is True
        ):
            logger.info(f"推送成功: {item['tweet_url']}")
            return [item]
        logger.warning(f"推送失败 ({response.status_code}): {item['tweet_url']}")
    except (requests.RequestException, ValueError, TypeError) as error:
        logger.error(f"请求异常：{error} - {item['tweet_url']}")
    return []


def _send_media_group(group):
    sent_items = []
    for start in range(0, len(group), TELEGRAM_ALBUM_MAX):
        chunk = group[start : start + TELEGRAM_ALBUM_MAX]
        if len(chunk) == 1:
            sent_items.extend(_send_photo(chunk[0]))
            continue
        media = [
            {"type": "photo", "media": item["media_url"]} for item in chunk
        ]
        media[0]["caption"] = chunk[0]["tweet_url"]
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{bottoken}/sendMediaGroup",
                data={
                    "chat_id": chatid,
                    "media": json.dumps(media),
                },
                timeout=(10, 30),
            )
            response_data = response.json()
            if (
                response.status_code == 200
                and isinstance(response_data, dict)
                and response_data.get("ok") is True
            ):
                logger.info(
                    f"相册推送成功: {chunk[0]['tweet_url']}（{len(chunk)} 张）"
                )
                sent_items.extend(chunk)
            else:
                logger.warning(
                    f"相册推送失败 ({response.status_code}): {chunk[0]['tweet_url']}"
                )
        except (requests.RequestException, ValueError, TypeError) as error:
            logger.error(f"相册请求异常：{error} - {chunk[0]['tweet_url']}")
    return sent_items


def push(data):
    success_hashes = []
    processed = 0
    total = len(data)

    for _, group in itertools.groupby(data, key=lambda item: item["id"]):
        group = list(group)
        if len(group) == 1:
            sent_items = _send_photo(group[0])
        else:
            sent_items = _send_media_group(group)
        success_hashes.extend(hash_item(item) for item in sent_items)

        processed += len(group)
        if processed % PUSH_BATCH_SIZE == 0 and processed < total:
            logger.info(f"已推送 {processed} 条，暂停 {PUSH_BATCH_SLEEP} 秒...")
            time.sleep(PUSH_BATCH_SLEEP)

    return success_hashes


def main():
    state = load_saved_data(STATE_FILE)
    is_first_run = not state.get("initialized", False)

    logger.info("开始获取喜欢的帖子...")
    media_items = normalize_items(
        likes_client.get_liked_media(
            userid,
            max_pages=max_like_pages,
            page_size=like_page_size,
        )
    )
    for warning in likes_client.last_warnings:
        logger.warning(f"X Likes 警告: {warning}")
    if is_first_run and likes_client.last_warnings:
        raise RuntimeError("首次初始化获取不完整，本轮不写入状态，请稍后重试")
    logger.info(f"获取完成，本次共 {len(media_items)} 条媒体记录。")

    pushed_hashes = set(state.get("pushed_hashes", []))

    if is_first_run:
        logger.info("首次运行，初始化去重状态，不推送历史内容。")
        pushed_hashes.update(hash_item(item) for item in media_items)
    else:
        differences = get_differences(media_items, pushed_hashes)
        if not differences:
            logger.info("无新内容，无需推送。")
        else:
            logger.info(f"发现 {len(differences)} 条新内容，开始推送...")
            success_hashes = push(differences)
            pushed_hashes.update(success_hashes)
            logger.info(f"本轮推送成功 {len(success_hashes)} 条。")

    state["pushed_hashes"] = sorted(pushed_hashes)
    state["last_items"] = media_items
    state["initialized"] = True

    save_state(STATE_FILE, state)
    logger.info(f"状态已更新：累计去重指纹 {len(state['pushed_hashes'])} 条。")


def run():
    logger.info("推送服务启动。")
    while True:
        round_start = time.time()
        try:
            main()
        except Exception as error:
            logger.exception(f"本轮执行失败：{error}")
        logger.info(
            f"本轮耗时 {time.time() - round_start:.1f} 秒，"
            f"等待 {sleeptime} 秒后执行下一轮。"
        )
        time.sleep(sleeptime)


if __name__ == "__main__":
    setup_logging()
    run()
