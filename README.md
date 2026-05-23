# VoiceTODocument · 语音转文档

> 🎙️ 基于讯飞大模型的录音文件批量转写工具，支持 202 种方言免切识别

[English](READEME_EN.md)

---

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [使用方法](#使用方法)
- [输出说明](#输出说明)
- [技术原理](#技术原理)
- [常见问题](#常见问题)

---

## 项目简介

本工具调用讯飞开放平台的录音文件转写大模型 API，将 `.m4a`、`.wav`、`.mp3` 等格式的录音文件自动转换为带时间戳的 JSON 和纯文本 TXT。特别针对方言场景（如山东临沂方言）开启 `autodialect` 模式，无需预先指定语种即可自动识别 202 种方言。

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 🗣️ **方言免切** | `autodialect` 模式，自动识别 202 种方言，无需手动指定 |
| 📂 **批量处理** | 递归扫描 `RawRecords/` 下所有音频，逐个自动转写 |
| 📄 **双格式输出** | 每个音频生成完整 JSON（含时间戳）+ 纯文本 TXT |
| 🔐 **HMAC 签名** | SHA1 + Base64 安全签名，保障 API 调用安全 |
| 📁 **保留目录结构** | `RawRecords/` 中的子目录层级自动镜像到 `Results/` |
| ⏱️ **容错轮询** | 每 20 秒查询进度，失败文件不影响后续处理 |

---

## 项目结构

```text
VoiceTODocument/
├── RawRecords/                       # 待转写音频放入此目录
│   ├── 录音1.m4a                     # 支持 m4a / wav / mp3 等格式
│   ├── 录音2.wav
│   └── 子目录/                       # 支持子文件夹，层级自动保留
│       └── 录音3.mp3
├── Results/                          # 转写结果输出（自动创建）
│   ├── 录音1.json                    # 完整结果（含时间戳、置信度）
│   ├── 录音1.txt                     # 纯文本结果
│   └── 子目录/
│       ├── 录音3.json
│       └── 录音3.txt
├── multi_records_transcribe_llm.py   # 批量转写入口（推荐）
├── xfyun_transcribe_llm.py           # 单文件转写脚本
├── requirements.txt                  # Python 依赖清单
└── .env                              # API 密钥配置（需自行创建）
```

---

## 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.8 | — |
| requests | ≥ 2.20.0 | HTTP 上传 + 轮询 |
| python-dotenv | ≥ 0.19.0 | 读取 `.env` 密钥 |

安装：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 快速开始

### 1. 获取 API 密钥

前往 [讯飞开放平台控制台](https://console.xfyun.cn/services)，开通「语音转写」服务，获取三项凭证：

- **APP_ID**
- **API_KEY**
- **API_SECRET**

### 2. 配置 `.env`

在项目根目录创建 `.env` 文件：

```bash
APP_ID=你的APPID
API_KEY=你的APIKey
API_SECRET=你的APISecret
```

### 3. 放入音频文件

将需要转写的录音文件放入 `RawRecords/` 目录（支持子文件夹）。

### 4. 运行批量转写

```bash
python multi_records_transcribe_llm.py
```

---

## 使用方法

### 批量转写（推荐）

```bash
python multi_records_transcribe_llm.py
```

自动扫描 `RawRecords/` 下所有音频，逐个上传并轮询结果，输出到 `Results/`。

### 单个文件转写

修改 `xfyun_transcribe_llm.py` 中的 `AUDIO_FILE` 变量指向目标文件，然后：

```bash
python xfyun_transcribe_llm.py
```

---

## 输出说明

每个音频文件生成两个结果文件：

### `.json` — 完整转写结果

```json
{
  "lattice": [
    {
      "json_1best": "{\"st\":{\"rt\":[{\"ws\":[{\"cw\":[{\"w\":\"你好\"}]}]}]}}"
    }
  ]
}
```

包含时间戳、置信度、说话人分离等完整信息。

### `.txt` — 纯文本

```txt
用两小时之内发它是吧？
对呀对对对
啊用它是吧？好了，也就是说咱今天中午...
```

已从 JSON 中提取并拼接为可读段落，方便直接编辑使用。

---

## 技术原理
音频文件 ──上传──▶ 讯飞服务器 ──转写──▶ 轮询获取结果 ──▶ JSON + TXT

1. **上传**：将音频以 `application/octet-stream` 流式上传至 `office-api-ist-dx.iflyaisol.com/v2/upload`
2. **签名认证**：每步请求通过 HMAC-SHA1 + Base64 生成 `signature`，参数按字典序排序后拼接再签名
3. **轮询**：上传后获得 `orderId`，每 20 秒调用 `/v2/getResult` 查询状态
4. **状态机**：
   - `1` — 音频解析中
   - `3` — 转写处理中
   - `4` — 转写完成
   - `-1` — 转写失败
5. **结果提取**：从 `lattice` → `json_1best` → `st.rt.ws.cw.w` 逐层解析词级结果

### 方言支持参数

| 参数 | 值 | 说明 |
|------|------|------|
| `language` | `autodialect` | 自动方言识别，覆盖 202 种方言 |
| `roleType` | `1` | 开启说话人分离 |
| `eng_smoothproc` | `true` | 英文平滑处理 |
| `eng_colloqproc` | `true` | 英文口语规范化 |

---

## 常见问题

**Q: 支持哪些音频格式？**  
A: `.m4a` `.wav` `.mp3` `.pcm` `.amr` `.speex` `.flac` `.aac` `.ogg` `.wma` 均支持。

**Q: 转写需要多长时间？**  
A: 约等于音频时长的 1/5 ~ 1/3。1 小时录音通常等待 10-20 分钟。

**Q: 文件大小有限制吗？**  
A: 单文件最大 500MB（讯飞官方限制）。

**Q: 报 `signature is error`？**  
A: 检查 `.env` 中 `API_KEY` 和 `API_SECRET` 是否填写正确，且与 `APP_ID` 属于同一应用。

---

## License

MIT License
