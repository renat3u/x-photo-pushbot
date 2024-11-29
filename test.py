import json
from twitter.scraper import Scraper

# 设置需要提取的推文数量
length = 5  # 可以修改为你想要提取的数量

scraper = Scraper(cookies={
    "ct0": '6818ada1faa590a7f7ae5a602d9e41dcab599a2759f0f69c1d354feb7c027c227a1a2b68ba6a6735c9005334eb20fd696ff0c0299d43e225c40cacc1bc74711316c8ffd67129868f197a2304bf7e334d',
    "auth_token": '348afbe69508f67eb0f62382916222e4555d98e5'
})

likes = scraper.likes([1288320315341148160])

media_urls = []

# 遍历喜欢的推文并提取信息
count = 0
for like in likes:
    if 'data' in like and 'user' in like['data'] and 'result' in like['data']['user']:
        timeline = like['data']['user']['result'].get('timeline_v2', {}).get('timeline', {})
        if 'instructions' in timeline:
            for instruction in timeline['instructions']:
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
                                        media_urls.append([conversation_id_str, expanded_url, media_url_https])
                                        count += 1
                                        if count >= length:
                                            break
                        if count >= length:
                            break
                if count >= length:
                    break
        if count >= length:
            break

# 将提取的结果写入到 JSON 文件
data = {'data': media_urls}  # 格式化为 {'data': [...]}

with open('results.json', 'w') as f:
    json.dump(data, f, indent=4)

print(f"提取了 {len(media_urls)} 条媒体信息，并已写入到 results.json 文件。")
