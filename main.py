import json
import os
import shutil
import time
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
    except FileNotFoundError:
        print(f"File {file_path} not found. Returning empty list.")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from file {file_path}. Returning empty list.")
        return []


def get_differences(data, saved_data):
    data = data.get("data", [])
    saved_data = saved_data.get("data", [])

    data_ids = {
        item[0]
        for item in data
        if isinstance(item, list) and len(item) > 0 and isinstance(item[0], str)
    }
    saved_data_ids = {
        item[0]
        for item in saved_data
        if isinstance(item, list) and len(item) > 0 and isinstance(item[0], str)
    }

    differences_ids = data_ids.symmetric_difference(saved_data_ids)

    differences = [
        item
        for item in data
        if isinstance(item, list) and len(item) > 0 and item[0] in differences_ids
    ]
    differences.extend(
        [
            item
            for item in saved_data
            if isinstance(item, list) and len(item) > 0 and item[0] in differences_ids
        ]
    )

    return differences


def get_liked_tweets():
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
                            if "content" in entry:
                                tweet = (
                                    entry["content"]
                                    .get("itemContent", {})
                                    .get("tweet_results", {})
                                    .get("result", {})
                                )
                                if "legacy" in tweet:
                                    conversation_id_str = tweet["legacy"].get(
                                        "conversation_id_str"
                                    )
                                    entities = tweet["legacy"].get("entities", {})

                                    for media in entities.get("media", []):
                                        expanded_url = media.get("expanded_url")
                                        media_url_https = media.get("media_url_https")
                                        if expanded_url and media_url_https:
                                            media_urls.append(
                                                [
                                                    conversation_id_str,
                                                    expanded_url,
                                                    media_url_https,
                                                ]
                                            )

    return media_urls


def push(json_data):
    for item in json_data:
        if isinstance(item, list) and len(item) >= 3:
            tweeturl = item[1]
            photourl = item[2]
            if tweeturl and photourl:
                push = requests.post(
                    f"https://api.telegram.org/bot{bottoken}/sendPhoto",
                    data={"chat_id": chatid, "caption": tweeturl, "photo": photourl},
                )

                if push.status_code == 200:
                    print("推送成功")
                else:
                    print("推送失败")


def main():
    file_path = "pre_results.json"
    saved_data = load_saved_data(file_path)
    if saved_data == []:
        print("数组为空，将初始化，不执行其他操作")
        media_urls = get_liked_tweets()
        data = {"data": media_urls}
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
        print(f"提取了 {len(media_urls)} 条媒体信息，并已写入到 pre_results.json 文件")
        exit()

    media_urls = get_liked_tweets()
    data = {"data": media_urls}
    differences = get_differences(data, saved_data)
    if differences == []:
        print("无变化，无需推送")
    else:
        push(differences)

    if os.path.exists("./data"):
        shutil.rmtree("./data")

    data = {"data": media_urls}
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
        print(f"提取了 {len(media_urls)} 条媒体信息，并已写入到 pre_results.json 文件")


def run():
    while True:
        main()
        time.sleep(sleeptime)


if __name__ == "__main__":
    run()
