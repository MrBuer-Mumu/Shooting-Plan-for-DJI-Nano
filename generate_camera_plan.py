import requests
import json
import os
import time

# ===================== 环境变量读取 =====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")
SERVERCHAN_SENDKEY = os.getenv("SENDKEY")

# 坐标 新乡红旗↔延津
LON, LAT = 113.92, 35.31
TIMEOUT_SEC = 25
RETRY_TIMES = 2

# 【修复1：全局定义提示词，消除未定义报错】
SYSTEM_PROMPT = """
你是专业车载通勤拍摄指导。
拍摄设备DJI Osmo Nano固定在汽车前挡风玻璃，早6:40红旗→延津，晚18:05延津→红旗。
输出规则：
1. 分早晚两个通勤时段，依次写环境评估、光照逆光、拍摄参数、运镜延时、车载实操提醒；
2. 适配微信手机阅读，段落空行，不用复杂表格；
3. 禁止无人机、手持、飞行等词汇；
4. 阴雨、起雾、强光给出对应防眩光/除雾/ND建议；
5. 输出开头标注线路标识：DeepSeek主线路 / Gemini备用线路。
"""

def safe_parse_json(response):
    text = response.text.strip()
    print(f"接口完整返回：\n=====\n{text[:1200]}\n=====\n")
    if not text:
        raise Exception("服务器返回空白内容")
    return json.loads(text)

def get_caiyun_weather():
    url = f"https://api.caiyunapp.com/v2.6/{CAIYUN_TOKEN}/{LON},{LAT}/weather?dailysteps=1&hourlysteps=24"
    print("【调用彩云天气】")
    resp = requests.get(url, timeout=TIMEOUT_SEC)
    return safe_parse_json(resp)

def call_deepseek(weather_json: str) -> str:
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
            print(f"DeepSeek第{attempt+1}次请求")
            resp = requests.post(api_url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
            res = safe_parse_json(resp)
            return "✅【主线路 DeepSeek 生成方案】\n\n" + res["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"DeepSeek失败：{str(e)}")
            if attempt < RETRY_TIMES:
                time.sleep(3)
                continue
    raise ConnectionError("DeepSeek全部重试失败")

def call_gemini(weather_json: str) -> str:
    full_prompt = SYSTEM_PROMPT + f"\n气象原始数据：{weather_json}\n直接输出拍摄方案正文"
    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
    for attempt in range(RETRY_TIMES + 1):
        try:
            print(f"Gemini第{attempt+1}次请求")
            resp = requests.post(api_url, json=payload, timeout=TIMEOUT_SEC)
            res = safe_parse_json(resp)
            return "⚠️【备用线路 Gemini 生成方案，主接口不可用】\n\n" + res["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"Gemini失败：{str(e)}")
            if attempt < RETRY_TIMES:
                time.sleep(3)
                continue
    raise ConnectionError("Gemini全部重试失败")

def generate_plan_auto_fallback(weather_data) -> str:
    weather_str = json.dumps(weather_data, ensure_ascii=False)
    try:
        print("===== 尝试优先调用 DeepSeek =====")
        return call_deepseek(weather_str)
    except Exception as e:
        print(f"\n===== DeepSeek失败原因:{str(e)}，切换Gemini =====")
        return call_gemini(weather_str)

# 【修复2：推送函数增加SENDKEY第一个入参】
def send_wechat_notice(sendkey, title, content):
    api_url = f"https://sctapi.ftqq.com/{sendkey}.send"
    data = {"title": title, "desp": content}
    try:
        resp = requests.post(api_url, data=data, timeout=25)
        print("推送接口返回：", resp.text)
        return True
    except Exception as err:
        print("推送网络异常：", str(err))
        return False

# ===================== 程序入口 =====================
if __name__ == "__main__":
    try:
        weather_info = get_caiyun_weather()
        plan_content = generate_plan_auto_fallback(weather_info)
        send_wechat_notice(SERVERCHAN_SENDKEY, "【每日通勤拍摄方案】", plan_content)
    except Exception as err:
        error_text = f"自动化脚本执行失败\n错误信息：{str(err)}"
        print("【最终捕获异常】", error_text)
        # 【修复3：异常推送补齐三个参数，不再缺content】
        send_wechat_notice(SERVERCHAN_SENDKEY, "⚠️通勤拍摄方案任务异常", error_text)
