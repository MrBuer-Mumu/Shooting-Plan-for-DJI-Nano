import requests
import json
import os

# ===================== 环境变量读取（密钥存Github Secrets，禁止硬编码） =====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CAIYUN_TOKEN = os.getenv("CAIYUN_TOKEN")
SERVERCHAN_SENDKEY = os.getenv("SERVERCHAN_SENDKEY")

# 固定配置
LON, LAT = 113.92, 35.31  # 新乡红旗区坐标
MORNING_TIME = "07:40"
EVENING_TIME = "18:20"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash"
# =========================================================================================

def get_caiyun_weather():
    """调用彩云天气API获取精细化气象数据"""
    url = f"https://api.caiyunapp.com/v2.6/{CAIYUN_TOKEN}/{LON},{LAT}/weather?dailysteps=1&hourlysteps=24"
    resp = requests.get(url, timeout=30)
    return resp.json()

def generate_drone_plan(weather_data, max_retry=2):
    """DeepSeek 生成通勤手持拍摄方案，增加网络重试"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""
你是专业随身拍摄指导。
拍摄区域：河南新乡红旗区 ↔ 延津通勤道路
设备：DJI Osmo Nano口袋云台相机
关注两个通勤时段：早上{MORNING_TIME}、傍晚{EVENING_TIME}

依据彩云天气气象数据输出拍摄方案，结构清晰、适合手机阅读，包含：
1. 环境评估：大风、沙尘、大雨、浓雾环境下拍摄注意事项
2. 两个时段光照情况、逆光风险预判、自然光优缺点
3. 相机参数推荐：曝光、白平衡、运镜思路
4. 推荐拍摄运镜方式；判断当下天气是否适合拍摄延时短片
5. 通勤途中手持拍摄实操小提醒
禁止多余空话，使用分点排版。

气象数据：
{json.dumps(weather_data, ensure_ascii=False)}
"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "生成今日通勤手持拍摄方案"}
        ],
        "temperature": 0.7,
        "stream": False
    }
    for attempt in range(max_retry + 1):
        try:
            res = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=40)
            return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < max_retry:
                import time
                time.sleep(3)  # 等待3秒重试
                continue
            else:
                raise e

def send_wechat_notice(title, content):
    """Server酱 Turbo 推送微信消息"""
    push_url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
    data = {
        "title": title,
        "desp": content
    }
    requests.post(push_url, data=data)


if __name__ == "__main__":
    try:
        weather_info = get_caiyun_weather()
        plan_result = generate_drone_plan(weather_info)
        send_wechat_notice("【每日通勤航拍方案】", plan_result)
    except Exception as err:
        error_text = f"自动化脚本执行失败\n错误信息：{str(err)}"
        send_wechat_notice("⚠️航拍方案任务异常", error_text)
