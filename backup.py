"""
讯飞录音文件转写大模型 - 方言场景专用
支持 202 种方言免切识别，适合山东临沂等方言录音
"""
import json
import logging
import os
import time
import random
import string
import hmac
import hashlib
import base64
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, quote
 
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"已加载配置: {env_path}")
    else:
        logger.warning(f"配置文件不存在: {env_path}，请检查密钥配置")
except ImportError:
    pass

APP_ID = os.getenv('APP_ID', '')
ACCESS_KEY_ID = os.getenv('API_KEY', '')
ACCESS_KEY_SECRET = os.getenv('API_SECRET', '')
AUDIO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'DaddyBusiness1.m4a')
TZ = timezone(timedelta(hours=8))

BASE_URL = 'https://office-api-ist-dx.iflyaisol.com'


def generate_signature(params: dict, secret: str) -> str:
    sorted_params = sorted(params.items())
    parts = []
    for k, v in sorted_params:
        if v is not None and v != '':
            parts.append(f"{k}={quote(str(v), safe='')}")
    base_string = '&'.join(parts)
    logger.debug(f"baseString: {base_string}")
    sig = hmac.new(secret.encode('utf-8'), base_string.encode('utf-8'), hashlib.sha1).digest()
    return base64.b64encode(sig).decode('utf-8')


def rand_str(n=16):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


def now_str():
    return datetime.now(TZ).strftime('%Y-%m-%dT%H:%M:%S+0800')


def upload(file_path: str):
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    sig_random = rand_str()
    dt = now_str()

    params = {
        'appId': APP_ID,
        'accessKeyId': ACCESS_KEY_ID,
        'dateTime': dt,
        'signatureRandom': sig_random,
        'fileSize': str(file_size),
        'fileName': file_name,
        'language': 'autodialect',
        'durationCheckDisable': 'true',
        'eng_smoothproc': 'true',
        'eng_colloqproc': 'true',
        'roleType': '1',
        'roleNum': '0',
    }

    sig = generate_signature(params, ACCESS_KEY_SECRET)
    qs = urlencode(params)
    url = f"{BASE_URL}/v2/upload?{qs}"

    logger.info(f"上传中... (文件: {file_name}, 大小: {file_size / 1024 / 1024:.1f} MB)")

    headers = {
        'Content-Type': 'application/octet-stream',
        'signature': sig,
    }
    with open(file_path, 'rb') as f:
        resp = requests.post(url, data=f, headers=headers, timeout=600)

    data = resp.json()
    if data.get('code') != '000000':
        raise Exception(f"上传失败: {json.dumps(data, ensure_ascii=False)}")

    order_id = data['content']['orderId']
    eta = data['content'].get('taskEstimateTime', 0)
    logger.info(f"上传成功! orderId={order_id}, 预估 {eta / 1000:.0f} 秒后完成")
    return order_id, sig_random


def query(order_id: str, sig_random: str):
    dt = now_str()

    params = {
        'accessKeyId': ACCESS_KEY_ID,
        'dateTime': dt,
        'signatureRandom': sig_random,
        'orderId': order_id,
        'resultType': 'transfer',
    }

    sig = generate_signature(params, ACCESS_KEY_SECRET)
    qs = urlencode(params)
    url = f"{BASE_URL}/v2/getResult?{qs}"

    headers = {
        'Content-Type': 'application/json',
        'signature': sig,
    }
    resp = requests.post(url, json={}, headers=headers, timeout=60)
    return resp.json()


def save_result(result: dict, output_dir: str):
    order_result = result['content'].get('orderResult', '')
    if not order_result:
        logger.warning("无转写结果")
        return

    data = json.loads(order_result)

    json_path = os.path.join(output_dir, 'result_讯飞大模型_完整.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"完整 JSON 已保存: {json_path}")

    txt_path = os.path.join(output_dir, 'result_讯飞大模型_纯文本.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        for seg in data.get('lattice', []):
            raw = seg.get('json_1best', '')
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                words = []
                for rt in obj.get('st', {}).get('rt', []):
                    for ws in rt.get('ws', []):
                        for cw in ws.get('cw', []):
                            w = cw.get('w', '')
                            if w:
                                words.append(w)
                line = ''.join(words).strip()
                if line:
                    f.write(line + '\n')
            except (json.JSONDecodeError, KeyError):
                pass

    logger.info(f"纯文本已保存: {txt_path}")


def main():
    file_path = os.path.abspath(AUDIO_FILE)
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return

    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
        logger.error("密钥未配置，请检查 .env 文件中的 API_KEY 和 API_SECRET")
        return

    output_dir = os.path.dirname(file_path)

    try:
        order_id, sig_random = upload(file_path)
    except Exception as e:
        logger.error(f"上传异常: {e}")
        return

    logger.info("开始轮询转写结果（2小时录音预计等待 10-20 分钟）...")
    count = 0

    while True:
        count += 1
        result = query(order_id, sig_random)

        if result.get('code') != '000000':
            logger.error(f"查询报错: {json.dumps(result, ensure_ascii=False)}")
            break

        status = result['content']['orderInfo']['status']

        if status == 4:
            logger.info("转写完成!")
            save_result(result, output_dir)
            break
        elif status == -1:
            logger.error(f"转写失败! {json.dumps(result, ensure_ascii=False, indent=2)}")
            break
        elif status == 3:
            if count % 4 == 1:
                logger.info(f"处理中... (已等待 {count * 20} 秒)")
            time.sleep(20)
        else:
            logger.info(f"状态码: {status}, 等待中...")
            time.sleep(20)


if __name__ == '__main__':
    main()