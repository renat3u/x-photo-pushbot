from twitter.scraper import Scraper

# 设置需要提取的推文数量
length = 5  # 可以修改为你想要提取的数量

scraper = Scraper(cookies={
    "ct0": '',
    "auth_token": ''
})

likes = scraper.likes([1288320315341148160])

media_urls = []

# 遍历喜欢的推文并提取信息
count = 0
for like in likes:
    if 'data' in like and 'user' in like['data'] and 'result' in like['data']['user']:
        timeline = like['data']['user']['result'].get('timeline_v2', {}).get('timeline', {})
        if 'instructions' in timeline:
            for instruction in reversed(timeline['instructions']):
                if 'entries' in instruction:
                    for entry in instruction['entries']:
                        if 'content' in entry:
                            tweet = entry['content'].get('itemContent', {}).get('tweet_results', {}).get('result', {})
                            if 'legacy' in tweet:
                                # 检查 'entities' 和 'extended_entities' 中的 media 信息
                                conversation_id_str = tweet['legacy'].get('conversation_id_str')
                                entities = tweet['legacy'].get('entities', {})
                                
                                # 提取 media 中的信息
                                for media in entities.get('media', []):
                                    expanded_url = media.get('expanded_url')
                                    media_url_https = media.get('media_url_https')
                                    if expanded_url and media_url_https:
                                        # media_urls.append({'conversation_id_str': conversation_id_str,'expanded_url': expanded_url, 'media_url_https': media_url_https})
                                        with open('results.txt', 'w') as f:
                                            f.write(f"conversation_id_str: {conversation_id_str}\n")
                                            f.write(f"expanded_url: {expanded_url}\n")
                                            f.write(f"media_url_https: {media_url_https}\n")
                                            f.write("\n")
                                        

# 将提取的结果写入到文件
print(f"提取了最新的帖子信息，并已写入到 results.txt 文件。")

