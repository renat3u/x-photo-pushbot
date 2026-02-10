import json
import os
import shutil
import time
import hashlib
from twitter.scraper import Scraper
import requests


userid = 114514
bottoken = "114514:ABCDEFG"
chatid = "-1001006503122"
sleeptime = 86400
media_urls = []
STATE_VERSION = 2

scraper = Scraper(
    cookies={
        "ct0": "1145",
        "auth_token": "14",
    }
)


def hash_item(item):
    raw = f"{item['id']}|{item['media_url']}"
    return hashlib.md5(raw.encode()).hexdigest()


def normalize_items(items):
    unique_items = {}
    for item in items:
        item_hash = hash_item(item)
        unique_items[item_hash] = item
    return sorted(unique_items.values(), key=lambda x: (x["id"], x["media_url"]))


def load_saved_data(file_path):
    """
    支持两种格式：
    1) 旧版: [ {id, media_url, tweet_url}, ... ]
    2) 新版: {"version": 2, "pushed_hashes": [...], "last_items": [...]}
    """
    default_state = {"version": STATE_VERSION, "pushed_hashes": [], "last_items": []}

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            raw = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_state

    # 兼容旧版列表结构
    if isinstance(raw, list):
        items = normalize_items(raw)
        return {
            "version": STATE_VERSION,
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
            "pushed_hashes": sorted(set(pushed_hashes)),
            "last_items": normalize_items(last_items),
        }

    return default_state


def save_state(file_path, state):
    safe_state = {
        "version": STATE_VERSION,
        "pushed_hashes": sorted(set(state.get("pushed_hashes", []))),
        "last_items": normalize_items(state.get("last_items", [])),
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(safe_state, f, indent=4, ensure_ascii=False)


def get_differences(new_data, pushed_hashes):
    pushed_hashes_set = set(pushed_hashes)
    new_items = []
    for item in normalize_items(new_data):
        if hash_item(item) not in pushed_hashes_set:
            new_items.append(item)
    return new_items


def get_liked_tweets():
    media_items = []
    likes = scraper.likes([userid])
    for like in likes:
        if (
            "data" in like
            and "user" in like["data"]
            and "result" in like["data"]["user"]
        ):
            timeline = (
                like["data"]["user"]["result"]
                .get("timeline_v2", {})
                .get("timeline", {})
            )
            if "instructions" in timeline:
                for instruction in timeline["instructions"]:
                    if "entries" in instruction:
                        for entry in instruction["entries"]:
                            tweet = (
                                entry.get("content", {})
                                .get("itemContent", {})
                                .get("tweet_results", {})
                                .get("result", {})
                            )
                            legacy = tweet.get("legacy", {})
                            tweet_id = legacy.get("conversation_id_str")
                            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
                            media_list = legacy.get("entities", {}).get("media", [])
                            for media in media_list:
                                media_url = media.get("media_url_https")
                                if tweet_id and media_url:
                                    media_items.append({
                                        "id": tweet_id,
                                        "media_url": media_url,
                                        "tweet_url": tweet_url
                                    })
    return normalize_items(media_items)


def push(data):
    count = 0
    success_hashes = []

    for item in data:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{bottoken}/sendPhoto",
                data={
                    "chat_id": chatid,
                    "caption": item["tweet_url"],
                    "photo": item["media_url"]
                }
            )
            if response.status_code == 200:
                print(f"推送成功: {item['tweet_url']}")
                success_hashes.append(hash_item(item))
            else:
                print(f"推送失败 ({response.status_code}): {item['tweet_url']}")
        except requests.RequestException as e:
            print(f"请求异常：{e} - {item['tweet_url']}")

        count += 1
        if count % 20 == 0:
            print("已推送20条，暂停30秒...")
            time.sleep(30)

    return success_hashes


def safe_remove_dir(path):
    if os.path.exists(path) and os.path.isdir(path):
        try:
            shutil.rmtree(path)
        except Exception as e:
            print(f"无法删除目录 {path}: {e}")


def main():
    file_path = "pre_results.json"
    state = load_saved_data(file_path)

    print("开始获取喜欢的帖子...")
    media_items = get_liked_tweets()
    print(f"获取完成，本次共 {len(media_items)} 条媒体记录。")

    pushed_hashes = set(state.get("pushed_hashes", []))
    is_first_run = len(pushed_hashes) == 0

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

    safe_remove_dir("./data")
    save_state(file_path, state)
    print(f"状态已更新：累计去重指纹 {len(state['pushed_hashes'])} 条。")


def run():
    while True:
        main()
        time.sleep(sleeptime)


if __name__ == "__main__":
    run()
