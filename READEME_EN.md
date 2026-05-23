# VoiceTODocument · Speech to Document

> 🎙️ Batch audio-to-text transcription powered by iFlytek LLM API, with support for 202 dialects

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Output](#output)
- [How It Works](#how-it-works)
- [FAQ](#faq)

---

## Overview

This tool calls iFlytek's long-form audio transcription LLM API to batch-convert audio files (`.m4a`, `.wav`, `.mp3`, etc.) into timestamped JSON and plain text TXT. It features `autodialect` mode, enabling automatic recognition of 202 dialects without manually specifying the language — ideal for regional dialect recordings.

---

## Features

| Feature | Description |
|------|------|
| 🗣️ **Auto Dialect Detection** | `autodialect` mode recognizes 202 dialects automatically |
| 📂 **Batch Processing** | Recursively scans `RawRecords/` and transcribes all audio files |
| 📄 **Dual-format Output** | Each file produces a full JSON (with timestamps) + plain text TXT |
| 🔐 **HMAC Signing** | SHA1 + Base64 signature for secure API calls |
| 📁 **Preserves Directory Structure** | Subdirectories under `RawRecords/` are mirrored to `Results/` |
| ⏱️ **Fault-tolerant Polling** | Queries progress every 20s; failed files won't block the rest |

---

## Project Structure

```text
VoiceTODocument/
├── RawRecords/                       # Place audio files here
│   ├── recording1.m4a                # Supports m4a / wav / mp3 etc.
│   ├── recording2.wav
│   └── subfolder/                    # Subfolders preserved in output
│       └── recording3.mp3
├── Results/                          # Transcription output (auto-created)
│   ├── recording1.json               # Full result (timestamps, confidence)
│   ├── recording1.txt                # Plain text result
│   └── subfolder/
│       ├── recording3.json
│       └── recording3.txt
├── multi_records_transcribe_llm.py   # Batch entry script (recommended)
├── xfyun_transcribe_llm.py           # Single-file script
├── requirements.txt                  # Python dependencies
└── .env                              # API credentials (create manually)
```

---

## Requirements

| Dependency | Version | Purpose |
|------|------|------|
| Python | ≥ 3.8 | — |
| requests | ≥ 2.20.0 | HTTP upload + polling |
| python-dotenv | ≥ 0.19.0 | Load `.env` credentials |

Install:

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## Quick Start

### 1. Get API Credentials

Go to [iFlytek Open Platform Console](https://console.xfyun.cn/services), enable the **Speech Transcription** service, and obtain:

- **APP_ID**
- **API_KEY**
- **API_SECRET**

### 2. Configure `.env`

Create a `.env` file in the project root:

```bash
APP_ID=your_app_id
API_KEY=your_api_key
API_SECRET=your_api_secret
```

### 3. Add Audio Files

Place your audio recordings into the `RawRecords/` directory (subfolders are supported).

### 4. Run Batch Transcription

```bash
python multi_records_transcribe_llm.py
```

---

## Usage

### Batch Transcription (Recommended)

```bash
python multi_records_transcribe_llm.py
```

Automatically scans all audio files under `RawRecords/`, uploads and polls results one by one, writing output to `Results/`.

### Single File Transcription

Edit the `AUDIO_FILE` variable in `xfyun_transcribe_llm.py` to point to your target file, then:

```bash
python xfyun_transcribe_llm.py
```

---

## Output

Each audio file produces two result files:

### `.json` — Complete Transcription

```json
{
  "lattice": [
    {
      "json_1best": "{\"st\":{\"rt\":[{\"ws\":[{\"cw\":[{\"w\":\"Hello\"}]}]}]}}"
    }
  ]
}
```

Contains timestamps, confidence scores, speaker diarization, and all metadata.

### `.txt` — Plain Text

```txt
Hello
```
Contains the plain text version of the transcription, with no timestamps or metadata.


Extracted and joined into readable paragraphs, ready for editing.

---

## How It Works
Audio File ──upload──▶ iFlytek Server ──transcribe──▶ Poll for Results ──▶ JSON + TXT


1. **Upload**: Streams audio as `application/octet-stream` to `office-api-ist-dx.iflyaisol.com/v2/upload`
2. **Signature Authentication**: Each request signs parameters via HMAC-SHA1 + Base64, sorted lexicographically before signing
3. **Polling**: After upload, an `orderId` is returned; query `/v2/getResult` every 20 seconds
4. **State Machine**:
   - `1` — Parsing audio
   - `3` — Transcribing
   - `4` — Completed
   - `-1` — Failed
5. **Result Extraction**: Parses word-level results through `lattice` → `json_1best` → `st.rt.ws.cw.w`

### Dialect Support Parameters

| Parameter | Value | Description |
|------|------|------|
| `language` | `autodialect` | Auto-detect across 202 dialects |
| `roleType` | `1` | Enable speaker diarization |
| `eng_smoothproc` | `true` | English smoothing |
| `eng_colloqproc` | `true` | English colloquial normalization |

---

## FAQ

**Q: What audio formats are supported?**  
A: `.m4a` `.wav` `.mp3` `.pcm` `.amr` `.speex` `.flac` `.aac` `.ogg` `.wma` are all supported.

**Q: How long does transcription take?**  
A: Roughly 1/5 to 1/3 of the audio duration. A 1-hour recording typically takes 10–20 minutes.

**Q: Is there a file size limit?**  
A: 500 MB per file (iFlytek official limit).

**Q: Getting `signature is error`?**  
A: Verify that `API_KEY` and `API_SECRET` in `.env` are correct and belong to the same application as `APP_ID`.

---

## License

MIT