"""
批量语音转写脚本 - 讯飞大模型版
扫描 RawRecords 目录下所有音频文件，逐个转写并保存结果到 Results 目录
基于 office-api-ist-dx.iflyaisol.com 新接口，支持方言免切识别
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
from urllib.parse import urlencode, quote_plus

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
        logger.warning(f"配置文件不存在: {env_path}")
except ImportError:
    pass

APP_ID = os.getenv('APP_ID', '')
ACCESS_KEY_ID = os.getenv('API_KEY', '')
ACCESS_KEY_SECRET = os.getenv('API_SECRET', '')
TZ = timezone(timedelta(hours=8))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, 'RawRecords')
RESULT_DIR = os.path.join(BASE_DIR, 'Results')
BASE_URL = 'https://office-api-ist-dx.iflyaisol.com'

AUDIO_EXTENSIONS = {'.m4a', '.wav', '.mp3', '.pcm', '.amr', '.speex', '.flac', '.aac', '.ogg', '.wma'}


def generate_signature(params, secret):
    sorted_params = sorted(params.items())
    parts = []
    for k, v in sorted_params:
        if v is not None and v != '':
            parts.append(f"{k}={quote_plus(str(v), safe='')}")
    base_string = '&'.join(parts)
    sig = hmac.new(secret.encode('utf-8'), base_string.encode('utf-8'), hashlib.sha1).digest()
    return base64.b64encode(sig).decode('utf-8')


def rand_str(n=16):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


def now_str():
    return datetime.now(TZ).strftime('%Y-%m-%dT%H:%M:%S+0800')


def collect_audio_files(root_dir):
    audio_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                audio_files.append(os.path.join(dirpath, f))
    return sorted(audio_files)


def extract_plain_text(order_data):
    lines = []
    lattice = order_data.get('lattice', [])
    if not lattice and isinstance(order_data, dict):
        for v in order_data.values():
            if isinstance(v, list):
                lattice = v
                break

    for seg in lattice:
        if not isinstance(seg, dict):
            continue
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
                lines.append(line)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    return '\n'.join(lines)


def upload(file_path):
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

    logger.info(f"上传中... ({file_name}, {file_size / 1024 / 1024:.1f} MB)")
    headers = {'Content-Type': 'application/octet-stream', 'signature': sig}
    with open(file_path, 'rb') as f:
        resp = requests.post(url, data=f, headers=headers, timeout=600)
    data = resp.json()
    if data.get('code') != '000000':
        raise Exception(f"上传失败: {json.dumps(data, ensure_ascii=False)}")
    order_id = data['content']['orderId']
    eta = data['content'].get('taskEstimateTime', 0)
    logger.info(f"上传成功, orderId={order_id}, 预估 {eta / 1000:.0f} 秒")
    return order_id, sig_random


def query_result(order_id, sig_random):
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
    headers = {'Content-Type': 'application/json', 'signature': sig}
    resp = requests.post(url, json={}, headers=headers, timeout=60)
    return resp.json()


def process_file(file_path, output_dir):
    file_name = os.path.basename(file_path)
    base_name = os.path.splitext(file_name)[0]

    logger.info(f"=== 开始处理: {file_name} ===")

    try:
        order_id, sig_random = upload(file_path)
    except Exception as e:
        logger.error(f"上传异常 [{file_name}]: {e}")
        return False

    count = 0
    while True:
        count += 1
        try:
            result = query_result(order_id, sig_random)
        except Exception as e:
            logger.error(f"查询异常 [{file_name}]: {e}")
            return False

        if result.get('code') != '000000':
            logger.error(f"查询报错 [{file_name}]: {json.dumps(result, ensure_ascii=False)}")
            return False

        status = result['content']['orderInfo']['status']
        if status == 4:
            logger.info(f"转写完成 [{file_name}]")
            order_result = result['content']['orderResult']
            order_data = json.loads(order_result)

            json_path = os.path.join(output_dir, f'{base_name}.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(order_data, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON 已保存: {json_path}")

            txt_path = os.path.join(output_dir, f'{base_name}.txt')
            plain_text = extract_plain_text(order_data)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(plain_text)
            logger.info(f"文本已保存: {txt_path}")
            return True
        elif status == -1:
            fail_type = result['content']['orderInfo'].get('failType', 'unknown')
            logger.error(f"转写失败 [{file_name}], failType={fail_type}")
            return False
        elif status == 3:
            if count % 4 == 1:
                logger.info(f"处理中 [{file_name}]... (已等待 {count * 20} 秒)")
        elif status == 1:
            logger.info(f"音频解析中 [{file_name}]...")
        else:
            logger.info(f"状态 {status} [{file_name}], 等待...")
        time.sleep(20)


def main():
    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
        logger.error("密钥未配置，请检查 .env 文件中的 API_KEY 和 API_SECRET")
        return

    if not os.path.exists(RAW_DIR):
        logger.error(f"RawRecords 目录不存在: {RAW_DIR}")
        return

    audio_files = collect_audio_files(RAW_DIR)
    if not audio_files:
        logger.warning(f"未找到音频文件: {RAW_DIR}")
        return

    logger.info(f"找到 {len(audio_files)} 个音频文件")
    for f in audio_files:
        logger.info(f"  - {os.path.relpath(f, RAW_DIR)}")

    success = 0
    fail = 0

    for audio_path in audio_files:
        rel_path = os.path.relpath(audio_path, RAW_DIR)
        rel_dir = os.path.dirname(rel_path)
        output_dir = os.path.join(RESULT_DIR, rel_dir)
        os.makedirs(output_dir, exist_ok=True)

        if process_file(audio_path, output_dir):
            success += 1
        else:
            fail += 1

    logger.info(f"全部完成! 成功: {success}, 失败: {fail}")


if __name__ == '__main__':
    main()