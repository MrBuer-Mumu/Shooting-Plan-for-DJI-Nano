import requests
import json
import os
import time

# ===================== 环境变量读取 =====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CAIYUN_TOKEN = os.getenv("CAIYUN_TOKEN")
SERVERCHAN_SENDKEY = os.getenv("SERVERCHAN_SENDKEY")

# 坐标 新乡红旗区↔延津
LON, LAT = 113.92, 35.31
TIMEOUT_SEC = 25
RETRY_TIMES = 2  # 每个模型最大重试次数

# 统一固定提示词
SYSTEM_PROMPT = """
你是专业车载通勤拍摄指导。
拍摄区域：河南新乡红旗区 ↔ 延津县通勤道路
拍摄设备：DJI Osmo Nano，固定安装于汽车前挡风玻璃车内拍摄
实际通勤时间：
早间：06:40从红旗区出发，07:25到达延津
晚间：18:05从延津出发，18:45回到红旗区

依据气象数据输出通勤拍摄方案，手机友好清晰排版，分两个通勤时段，内容包含：
1. 环境拍摄评估：大风、沙尘、大雨、浓雾、逆光、路面反光、车窗起雾对拍摄影响；雨天重点提示镜头、车窗水汽
2. 早晚通勤光照、逆光风险、阳光角度对前挡风车内拍摄影响
3. Osmo Nano拍摄参数建议：曝光、白平衡、快门，适配车载固定机位
4. 运镜思路，判断是否适合录制延时短片
5. 车载机位实操小提醒

禁止出现无人机、飞行、手持等无关词汇，拒绝空洞话术，使用清晰分点。
"""

def safe_parse_json(response):
    """安全解析JSON，捕获空返回问题"""
    text = response.text.strip()
    print(f"接口完整返回内容：\n=====\n{text[:1200]}\n=====\n")
    if not text:
        raise Exception("接口返回空白内容，服务器无应答")
    return json.loads(text)

def get_caiyun_weather():
    """获取彩云天气数据"""
    url = f"https://api.caiyunapp.com/v2.6/{CAIYUN_TOKEN}/{LON},{LAT}?weather=daily&hourlysteps=24"
    resp = requests.get(url, timeout=TIMEOUT_SEC)
    print("【调用彩云天气】")
    return safe_parse_json(resp)


def call_deepseek(weather_json: str) -> str:
    """调用 DeepSeek"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"气象数据：{weather_json}\n生成今日通勤拍摄方案"}
        ],
        "temperature": 0.7,
        "stream": False
    }
    api_url = "https://api.deepseek.com/chat/completions"

    for attempt in range(RETRY_TIMES + 1):
        try:
            print(f"【DeepSeek 第{attempt+1}次发起请求】")
            resp = requests.post(api_url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
            res = safe_parse_json(resp)
            return res["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"DeepSeek 第{attempt+1}次请求失败：{str(e)}")
            if attempt < RETRY_TIMES:
                time.sleep(3)
                continue
    raise ConnectionError("DeepSeek 多次请求全部失败")


def call_gemini(weather_json: str) -> str:
    """备用：调用 Gemini Pro"""
    full_prompt = SYSTEM_PROMPT + f"\n气象原始数据：{weather_json}\n直接输出拍摄方案正文"
    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }

    for attempt in range(RETRY_TIMES + 1):
        try:
            print(f"【Gemini 第{attempt+1}次发起请求】")
            resp = requests.post(api_url, json=payload, timeout=TIMEOUT_SEC)
            res = safe_parse_json(resp)
            return res["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"Gemini 第{attempt+1}次请求失败：{str(e)}")
            if attempt < RETRY_TIMES:
                time.sleep(3)
                continue
    raise ConnectionError("Gemini 多次请求全部失败")


def generate_plan_auto_fallback(weather_data) -> str:
    """自动降级：优先DeepSeek，失败切换Gemini"""
    weather_str = json.dumps(weather_data, ensure_ascii=False)
    try:
        print("===== 尝试优先调用 DeepSeek =====")
        result = call_deepseek(weather_str)
        return "✅【主线路 DeepSeek 生成方案】\n\n" + result
    except Exception as e:
        print(f"\n===== DeepSeek 失败原因:{str(e)}，切换备用 Gemini =====")
        result = call_gemini(weather_str)
        return "⚠️【备用线路 Gemini 生成方案，主接口不可用】\n\n" + result


def send_wechat_notice(title, content):
    """Server酱微信推送"""
    push_url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
    data = {"title": title, "desp": content}
    requests.post(push_url, data, timeout=15)


# ===================== 程序入口 =====================
if __name__ == "__main__":
    try:
        weather_info = get_caiyun_weather()
        plan_content = generate_plan_auto_fallback(weather_info)
        send_wechat_notice("【每日通勤拍摄方案】", plan_content)
    except Exception as err:
        error_text = f"自动化脚本执行失败\n错误信息：{str(err)}"
        print("【最终捕获异常】", error_text)
        send_wechat_notice("⚠️通勤拍摄方案任务异常", error_text)
