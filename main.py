import os
import json
import requests
import feedparser
from openai import OpenAI
from datetime import datetime
import re # [新增] 用于处理文件名中的非法字符

# --- 配置区 ---
GIST_URL = os.environ.get("GIST_URL")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN") # 改用 PushPlus
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
HISTORY_FILE = "history.json"

# 初始化客户端
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.deepseek.com" if "deepseek" in str(OPENAI_API_KEY).lower() else None
)

# --- 辅助函数：发送微信消息 (PushPlus) ---
def send_wechat(title, content, link):
    url = "http://www.pushplus.plus/send"
    html_content = f"<h3>{title}</h3><p>{content}</p><br><a href='{link}'>阅读原文</a>"
    
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": "新情报捕获",
        "content": html_content,
        "template": "html"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"微信发送失败: {e}")

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
            model="deepseek-chat", 
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI分析失败: {str(e)}"

# --- [新增] 辅助函数：清理文件名 ---
def sanitize_filename(filename):
    # 移除 Windows 和 Linux 文件系统不允许的特殊字符
    safe_name = re.sub(r'[\\/*?:"<>|]', "", filename)
    # 限制文件名长度，防止过长报错，只取前40个字符作为关键字
    return safe_name[:40].strip()

# --- 主逻辑 ---
def main():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    else:
        history =[]

    print("正在获取情报源清单...")
    try:
        raw_content = requests.get(GIST_URL).text
        urls =[line.strip() for line in raw_content.split('\n') if line.strip() and not line.startswith('#')]
    except:
        print("获取 Gist 失败，请检查 GIST_URL Secret")
        return

    new_history = history.copy()
    
    for url in urls:
        print(f"正在巡逻: {url}")
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                latest_entry = feed.entries[0]
                link = latest_entry.link
                title = latest_entry.title
                
                if link in history:
                    print("  -> 已读，跳过")
                    continue
                
                print("  -> 发现新情报！正在分析...")
                summary = summarize_content(title, latest_entry.get('summary', '') or latest_entry.get('description', ''))
                
                if "无价值" not in summary:
                    # 1. 发送给微信
                    send_wechat(title, summary, link) 
                    
                    # 2. [新增] 保存为本地文件
                    today_date = datetime.now().strftime("%Y-%m-%d")
                    safe_title = sanitize_filename(title)
                    filename = f"{safe_title}_{today_date}.md" # 格式：关键字(标题)_日期.md
                    
                    try:
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(f"# {title}\n\n")
                            f.write(f"**日期**: {today_date}\n")
                            f.write(f"**原文链接**: {link}\n\n")
                            f.write(f"**AI 摘要**:\n{summary}\n")
                        print(f"  -> 已保存至文件: {filename}")
                    except Exception as e:
                        print(f"  -> 保存文件失败: {e}")

                    # 3. 记录到历史
                    new_history.append(link)
                else:
                    print("  -> AI 判定为无价值，已丢弃")
                
        except Exception as e:
            print(f"  -> 巡逻失败: {str(e)}")
            continue

    with open(HISTORY_FILE, "w") as f:
        json.dump(new_history[-500:], f)

if __name__ == "__main__":
    main()
