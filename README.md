# 自动获取指定账户喜欢的X帖子并进行推送

## 场景需求
自动获取目标用户（一般是自己）喜欢的帖子，从首次运行开始，每有新喜欢的图片帖子，使用Telegram Bot全自动发送图片和链接到指定频道，免去了手动保存图片与链接的麻烦.

## 使用方法
使用你喜欢的方法获取本仓库内容，确保本地安装了*Python 3.10.10*及更新版本，执行`pip install -r requirements.txt`安装依赖.

main.py各项参数说明如下：

|        参数        |   参考值   |            说明            |
| :--------------------: | :-----: | :--------------------------: |
| userid | 25073877 |    在目标用户主页，获取banner图片链接，第一项即为id.如https://pbs.twimg.com/profile_banners/25073877/1604214583/600x200 当中的25073877即为userid   |
| bottoken  |  114514:ABCDEFG | Telegram Bot的token |
| chatid  | -1001006503122 |    Bot发送的聊天ID，私聊为用户id（需要用户先发起会话），负数为频道或者群组（请确保已给予Bot管理员权限）    |
| sleeptime  | 86400  |    睡眠时间，单位为秒    |
| cookies  |         "ct0": "1145","auth_token": "14"  |    X的cookie    |

## 声明
- 本脚本使用的是trevorhobenshield开发的[twitter-api-client](https://github.com/trevorhobenshield/twitter-api-client/)，调用的为X官方的api，有Rate Limit，请勿滥用。
- 由于有Rate Limit，默认为半天运行一次脚本
- 本脚本仅供个人交流学习