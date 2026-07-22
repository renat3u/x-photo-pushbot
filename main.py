import json
import os
import time
import hashlib

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


def push(data):
    success_hashes = []

    for count, item in enumerate(data, start=1):
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
                print(f"推送成功: {item['tweet_url']}")
                success_hashes.append(hash_item(item))
            else:
                print(f"推送失败 ({response.status_code}): {item['tweet_url']}")
        except (requests.RequestException, ValueError, TypeError) as e:
            print(f"请求异常：{e} - {item['tweet_url']}")

        if count % 20 == 0 and count < len(data):
            print("已推送20条，暂停30秒...")
            time.sleep(30)

    return success_hashes


def main():
    state = load_saved_data(STATE_FILE)
    is_first_run = not state.get("initialized", False)

    print("开始获取喜欢的帖子...")
    media_items = normalize_items(
        likes_client.get_liked_media(
            userid,
            max_pages=max_like_pages,
            page_size=like_page_size,
        )
    )
    for warning in likes_client.last_warnings:
        print(f"X Likes 警告: {warning}")
    if is_first_run and likes_client.last_warnings:
        raise RuntimeError("首次初始化获取不完整，本轮不写入状态，请稍后重试")
    print(f"获取完成，本次共 {len(media_items)} 条媒体记录。")

    pushed_hashes = set(state.get("pushed_hashes", []))

    if is_first_run:
        print("首次运行，初始化去重状态，不推送历史内容。")
        pushed_hashes.update(hash_item(item) for item in media_items)
    else:
        differences = get_differences(media_items, pushed_hashes)
        if not differences:
            print("无新内容，无需推送。")
        else:
            print(f"发现 {len(differences)} 条新内容，开始推送...")
            success_hashes = push(differences)
            pushed_hashes.update(success_hashes)
            print(f"本轮推送成功 {len(success_hashes)} 条。")

    state["pushed_hashes"] = sorted(pushed_hashes)
    state["last_items"] = media_items
    state["initialized"] = True

    save_state(STATE_FILE, state)
    print(f"状态已更新：累计去重指纹 {len(state['pushed_hashes'])} 条。")


def run():
    while True:
        try:
            main()
        except Exception as error:
            print(f"本轮执行失败：{error}")
        print(f"等待 {sleeptime} 秒后执行下一轮。")
        time.sleep(sleeptime)


if __name__ == "__main__":
    run()
