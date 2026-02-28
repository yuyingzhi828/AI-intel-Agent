import os
import json
import requests
import feedparser
from openai import OpenAI
from datetime import datetime

# --- 配置区 (从环境变量读取) ---
GIST_URL = os.environ.get("GIST_URL") # 你的Gist Raw地址
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
HISTORY_FILE = "history.json"

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"), # 记得在 GitHub Secrets 里把名字也改了
    base_url="https://api.deepseek.com"
)

# --- 辅助函数：发送 Telegram 消息 ---
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# --- 辅助函数：AI 摘要 ---
def summarize_content(title, content):
    prompt = f"""
    你是我的情报分析师。请阅读以下文章片段，用中文简要总结核心观点（50字以内）。
    如果内容与'AI、编程、黑客技术、创业'无关，请直接回复'无价值'。
    
    标题：{title}
    内容片段：{content[:1500]}
    """
    try:
        response = client.chat.completions.create(
            #model="gpt-4o-mini", # 使用便宜的模型
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI分析失败: {str(e)}"

# --- 主逻辑 ---
def main():
    # 1. 读取历史记录 (防止重复发送)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    else:
        history = []

    # 2. 获取 Gist 中的源列表
    print("正在获取情报源清单...")
    raw_content = requests.get(GIST_URL).text
    # 过滤空行和注释
    urls = [line.strip() for line in raw_content.split('\n') if line.strip() and not line.startswith('#')]

    new_history = history.copy()
    
    # 3. 遍历每个 URL 进行巡逻
    for url in urls:
        print(f"正在巡逻: {url}")
        try:
            # 尝试用 RSS 解析
            feed = feedparser.parse(url)
            
            # 如果解析出条目
            if feed.entries:
                latest_entry = feed.entries[0]
                link = latest_entry.link
                title = latest_entry.title
                
                # 检查是否已处理过
                if link in history:
                    print("  -> 已读，跳过")
                    continue
                
                # 发现新情报！
                print("  -> 发现新情报！正在分析...")
                summary = summarize_content(title, latest_entry.get('summary', '') or latest_entry.get('description', ''))
                
                if "无价值" not in summary:
                    msg = f"📢 *新情报捕获*\n\n**{title}**\n\n📝 {summary}\n\n🔗 [阅读原文]({link})"
                    send_telegram(msg)
                    new_history.append(link)
                
        except Exception as e:
            print(f"  -> 巡逻失败: {str(e)}")
            continue

    # 4. 保存最新的历史记录 (保留最近500条即可)
    with open(HISTORY_FILE, "w") as f:
        json.dump(new_history[-500:], f)

if __name__ == "__main__":
    main()
