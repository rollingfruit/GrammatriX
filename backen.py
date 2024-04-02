# -- coding: utf-8 --
from flask_cors import CORS
from flask import Flask, request, jsonify, send_from_directory
from google.cloud import speech_v1 as speech
from google.oauth2 import service_account

import time
import json

from contextlib import contextmanager
import SparkApi

app = Flask(__name__)
CORS(app)

with open('api_keys/SparkApi.json', 'r') as file:
    SparkApiKey = json.load(file)

# 以下密钥信息从json文件获取
appid = SparkApiKey['appid']
api_key = SparkApiKey['api_key']
api_secret = SparkApiKey['api_secret']

# 用于配置大模型版本，默认“general/generalv2”
domain = "generalv3"  # v3.0版本
# 云端环境的服务地址
Spark_url = "ws://spark-api.xf-yun.com/v3.1/chat"

recording_count = 0  # 初始化录音计数
# 初始化一个全局变量来标记是否是第一次执行
is_first_execution = True

# 从json文件读取
credentials = service_account.Credentials.from_service_account_file('api_keys/service-account-file.json')
client = speech.SpeechClient(credentials=credentials)

text = []


# length = 0

def getText(role, content):
    jsoncon = {}
    jsoncon["role"] = role
    jsoncon["content"] = content
    text.append(jsoncon)
    return text


def getlength(text):
    length = 0
    for content in text:
        temp = content["content"]
        leng = len(temp)
        length += leng
    return length


def checklen(text):
    while (getlength(text) > 8000):
        del text[0]
    return text


@contextmanager
def timing(description: str = "操作"):
    start_time = time.time()
    yield
    elapsed_time = time.time() - start_time
    print(f"{description}: {elapsed_time:.2f} 秒")


@app.route('/')
def index():
    return app.send_static_file('front.html')


# 如果没有独立的前端服务器，使用该接口返回图片。
# 有独立的前端服务器的话，注释该接口。
@app.route('/img/<path:filename>')
def serve_image(filename):
    # 注意：此处假设图片都在 static/img 目录下
    return send_from_directory('static/img', filename)


@app.route('/upload-audio', methods=['POST'])
def upload_audio():
    # global recording, stream, recording_count, is_first_execution
    global recording_count, is_first_execution
    if 'audioData' in request.files:
        audio_file = request.files['audioData']
        recording_count += 1
        filename = f"recording_{recording_count}.mp3"
        # 如果需要保存
        # audio_file.save('audio_file/' + filename)
        print(f"Audio file '{filename}' has been saved.")
        # Here you can process the audio file as needed
        # ...
        # audio_file = None
        with timing("\n读取音频文件执行时间"):
            # 读取文件内容到audio_file中
            # with open(filename, 'rb') as f:
            #     audio_file = f.read()
            # recording = []  # Reset the recording list after saving
            # print(f'Recording stopped and saved, filename: {filename}')
            audio_file = audio_file.read()  # 读取二进制数据
            # 音频配置
            # 配置语音识别请求
            audio = speech.RecognitionAudio(content=audio_file)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                sample_rate_hertz=16000,
                language_code='en-US'
            )
        with timing("\n语音识别执行时间"):
            # 调用Google Speech-to-Text
            response = client.recognize(config=config, audio=audio)
            if response.results:
                transcript = response.results[0].alternatives[0].transcript
                # 后续处理
            else:
                print("No results returned from the speech recognition service.")

            # 获取识别结果
            transcript = response.results[0].alternatives[0].transcript
            print(f'Transcript: {transcript}')

        with timing("\nAI分析执行时间"):

            print(f'is_first_execution: {is_first_execution}')
            if is_first_execution:
                prompt = "\n请分析下面的英文段落是否有语法错误，并按照以下结构化步骤操作：首先，如果没有检测到语法错误，请表扬用户并表示准备接收下一次输入；其次，如果存在语法错误，请列出每个错误，并跟随一个用引号包裹的简短中文解释，最后给出三个与识别出的错误相关的填空练习题以帮助加强正确用法，附上练习题正确答案。确保所有指示部分都以支持性和教育性的语调呈现。\n "
                # prompt = "\n我们即将开启一个主题对话，旨在深入探讨一个特定领域的知识或问题。为了确保我们的交流既丰富又有洞见，请遵循以下指南：每次回复请使用英文，并确保每次回复至少包含40个单词，以便充分表达和探索观点。接下来开始对话。\n"
                Input = prompt + transcript
                # Input = transcript
                # 将is_first_execution设置为False，表示函数已被执行过一次
                is_first_execution = False
            else:
                Input = transcript
            # prompt = "\n请分析下面的英文段落是否有语法错误，并按照以下结构化步骤操作：首先，如果没有检测到语法错误，请表扬用户并表示准备接收下一次输入；其次，如果存在语法错误，请列出每个错误，并跟随一个用引号包裹的简短中文解释，最后给出三个与识别出的错误相关的填空练习题以帮助加强正确用法，附上练习题正确答案。确保所有指示部分都以支持性和教育性的语调呈现。\n "
            # Input = prompt + transcript
            # Input = "\n我: 请分析下面的英文段落是否有语法错误，并按照以下结构化步骤操作：首先，如果没有检测到语法错误，请表扬用户并表示准备接收下一次输入；其次，如果存在语法错误，请列出每个错误，并跟随一个用引号包裹的简短中文解释，最后给出三个与识别出的错误相关的填空练习题以帮助加强正确用法，附上练习题正确答案。确保所有指示部分都以支持性和教育性的语调呈现。\n " + transcript
            print("Input: ", Input)
            question = checklen(getText("user", Input))
            SparkApi.answer = ""
            print("AI纠错结果:", end="")
            SparkApi.main(appid, api_key, api_secret, Spark_url, domain, question)

        return jsonify({"message": "Recording stopped and saved", "filename": filename,
                        "transcript": transcript,
                        'assistant': SparkApi.answer})
    else:
        return "No audio data received.", 400


if __name__ == '__main__':
    app.run(debug=True, port=5001)
