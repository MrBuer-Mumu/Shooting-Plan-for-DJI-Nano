import requests
import json
import os
import time

# ===================== 环境变量读取（密钥存在Github Secrets，禁止硬编码） =====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CAIYUN_TOKEN = os.getenv("CAIYUN_TOKEN")
SERVERCHAN_SENDKEY = os.getenv("SERVERCHAN_SENDKEY")

# 固定配置
LON, LAT = 113.92, 35.31  # 新乡红旗区坐标
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash"

# ===================== 函数定义 =====================
def get_caiyun_weather():
    """调用彩云天气API获取精细化气象数据"""
    url = f"https://api.caiyunapp.com/v2.6/{CAIYUN_TOKEN}/{LON},{LAT}?weather=daily&hourlysteps=24"
    resp = requests.get(url, timeout=30)
    return resp.json()

def generate_camera_plan(weather_data, max_retry=2):
    """DeepSeek 生成通勤拍摄方案，增加网络重试"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""
你是专业车载通勤拍摄指导。
拍摄区域：河南新乡红旗区 ↔ 延津县通勤道路
拍摄设备：DJI Osmo Nano，固定安装于汽车前挡风玻璃进行车内拍摄
实际通勤时间：
早间：06:40从红旗区出发，07:25到达延津
晚间：18:05从延津出发，18:45回到红旗区

依据彩云天气气象数据输出通勤拍摄方案，结构清晰、适合手机阅读，严格区分两个通勤时段，内容包含：
1. 环境拍摄评估：大风、沙尘、大雨、浓雾、逆光、路面反光、车窗起雾等环境对拍摄的影响与注意事项；雨天重点提醒镜头防雨、车窗水汽问题
2. 两个通勤区间的光照情况、逆光风险预判、自然光特点、阳光照射角度对前挡拍摄的影响
3. Osmo Nano推荐拍摄参数：曝光、白平衡、快门思路；结合路况与光线给出适配车载机位的建议
4. 推荐运镜思路；判断当下天气、光线是否适合拍摄延时短片
5. 车载固定机位拍摄实操小提醒

禁止出现无人机、起飞、飞行、手持这类无关词汇，禁止空话，使用清晰分点排版。

气象数据：
{json.dumps(weather_data, ensure_ascii=False)}
"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "生成今日通勤拍摄方案"}
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
                time.sleep(3)  # 等待3秒重试
                continue
            else:
                raise e

def send_wechat_notice(title, content):
    """ServerChan Turbo 推送微信"""
    push_url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
    data = {
        "title": title,
        "desp": content
    }
    requests.post(push_url, data)

# ===================== 程序入口 =====================
if __name__ == "__main__":
    try:
        weather_info = get_caiyun_weather()
        plan_result = generate_camera_plan(weather_info)
        send_wechat_notice("【每日通勤拍摄方案】", plan_result)
    except Exception as err:
        error_text = f"自动化脚本执行失败\n错误信息：{str(err)}"
        send_wechat_notice("⚠️通勤拍摄方案任务异常", error_text)
