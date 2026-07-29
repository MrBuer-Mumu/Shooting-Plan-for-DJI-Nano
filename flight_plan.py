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
    resp = requests.get(url, timeout=20)
    return resp.json()

def generate_drone_plan(weather_data):
    """DeepSeek 生成通勤航拍方案"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""
你是专业航拍指导。
拍摄区域：河南新乡红旗区 ↔ 延津通勤道路
无人机：DJI Mini Nano，支持D-Log M，拥有ND8/ND16/ND32、黑柔滤镜
关注两个通勤时段：早上{MORNING_TIME}、傍晚{EVENING_TIME}

依据彩云天气气象数据输出拍摄方案，结构清晰、适合手机阅读，包含：
1. 飞行安全评估：风速＞8m/s不建议起飞；出现降雨、大雾、强阵风禁止飞行
2. 两个时段光照情况、逆光风险判断
3. 滤镜选择、推荐曝光参数（ISO、快门、EV）、D-Log M参数设置
4. 推荐运镜；判断是否适合拍摄延时
5. 道路航拍简短实操提醒
禁止多余空话，使用分点排版。

气象数据：
{json.dumps(weather_data, ensure_ascii=False)}
"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "生成今日通勤航拍拍摄方案"}
        ],
        "temperature": 0.7,
        "stream": False
    }
    res = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
    return res.json()["choices"][0]["message"]["content"]


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
