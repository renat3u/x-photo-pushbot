import requests
from requests_oauthlib import OAuth1
import os
import json  # 用于格式化输出
import tweepy
from twitter_api_client import Client

# 设置API凭证
API_KEY = 'Li3c6CA5Ya8m0Z5igLmwOL3xx'
API_SECRET_KEY = 'AvrfNyxrUdQQByHb3e6HQ7AfR2hTDiO1iQe9rN2rcI5QnRsR3k'
ACCESS_TOKEN = '1288320315341148160-jlenyR0wDz4LTMIRjtkikpvDKodDmb'
ACCESS_TOKEN_SECRET = '0BsrpW1Xize9FYIot0YvUERRyftye0J7AZ7wEEqjicULr'

auth = OAuth1(API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

proxies = {
    'http': '127.0.0.1:8847',
    'https': '127.0.0.1:8847'
}

client = Client(bearer_token=ACCESS_TOKEN)  # 使用 Bearer Token 进行认证

# 获取用户的点赞帖子并保存内容和媒体
def process_liked_tweets(user_id):
    # 获取用户的点赞帖子
    liked_tweets = client.get_liked_tweets(user_id=user_id, max_results=5)  # 获取最新5条点赞帖子
    if liked_tweets is not None and 'data' in liked_tweets:
        for tweet in liked_tweets['data']:
            tweet_id = tweet['id']
            tweet_content = tweet['text']
            tweet_url = f"https://twitter.com/{tweet['author_id']}/status/{tweet_id}"

            print(f"Processing Tweet ID: {tweet_id}")
            print(f"Tweet Content: {tweet_content}")
            print(f"Tweet URL: {tweet_url}")
            
            # 如果推文包含媒体，下载媒体文件
            if 'attachments' in tweet and 'media_keys' in tweet['attachments']:
                media_keys = tweet['attachments']['media_keys']
                for media_key in media_keys:
                    # 获取媒体文件信息
                    media = client.get_media(media_key=media_key)
                    if media and 'data' in media:
                        media_url = media['data']['url']
                        filename = f"{tweet_id}_{media_key}.jpg"  # 设置文件名
                        download_media(media_url, filename)
                        
            print("-" * 80)

# 下载媒体文件
def download_media(media_url, filename):
    try:
        # 发送请求并获取媒体内容
        response = requests.get(media_url, proxies=proxies)
        if response.status_code == 200:
            # 保存媒体文件
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded media file: {filename}")
        else:
            print(f"Failed to download media from {media_url}")
    except Exception as e:
        print(f"Error downloading media: {e}")

# 主函数，处理用户点赞的帖子
user_id = 'TARGET_USER_ID'  # 替换为目标用户的ID或用户名
process_liked_tweets(user_id)