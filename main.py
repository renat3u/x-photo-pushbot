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

scraper = Scraper(
    cookies={
        "ct0": "1145",
        "auth_token": "14",
    }
)


def load_saved_data(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def hash_item(item):
    raw = f"{item['id']}|{item['media_url']}"
    return hashlib.md5(raw.encode()).hexdigest()

def get_differences(new_data, saved_data):
    new_hashes = {hash_item(item): item for item in new_data}
    old_hashes = {hash_item(item): item for item in saved_data}

    new_only = [item for h, item in new_hashes.items() if h not in old_hashes]
    return new_only

def merge_items(existing_data, new_data):
    merged = {hash_item(item): item for item in existing_data}
    for item in new_data:
        merged[hash_item(item)] = item
    return sorted(merged.values(), key=lambda x: (x["id"], x["media_url"]))

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
    return media_items

def push(data):
    count = 0
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
            else:
                print(f"推送失败 ({response.status_code}): {item['tweet_url']}")
        except requests.RequestException as e:
            print(f"请求异常：{e} - {item['tweet_url']}")

        count += 1
        if count % 20 == 0:
            print("已推送20条，暂停30秒...")
            time.sleep(30)

def safe_remove_dir(path):
    if os.path.exists(path) and os.path.isdir(path):
        try:
            shutil.rmtree(path)
        except Exception as e:
            print(f"无法删除目录 {path}: {e}")

def main():
    file_path = "pre_results.json"
    saved_data = load_saved_data(file_path)

    media_items = get_liked_tweets()
    media_items = sorted(media_items, key=lambda x: (x["id"], x["media_url"]))

    if not saved_data:
        print("首次运行，初始化数据...")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(media_items, f, indent=4, ensure_ascii=False)
        print(f"已保存 {len(media_items)} 条数据。")
        return

    differences = get_differences(media_items, saved_data)
    if not differences:
        print("无新内容，无需推送。")
    else:
        print(f"发现 {len(differences)} 条新内容，开始推送...")
        push(differences)

    merged_data = merge_items(saved_data, media_items)

    safe_remove_dir("./data")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, indent=4, ensure_ascii=False)
        print(f"当前媒体信息已更新，共 {len(merged_data)} 条。")

def run():
    while True:
        main()
        time.sleep(sleeptime)

if __name__ == "__main__":
    run()
