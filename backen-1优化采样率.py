from flask import Flask, jsonify
from flask_cors import CORS
import sounddevice as sd
import soundfile as sf
import numpy as np
from flask import Flask, request, jsonify
import os
from google.cloud import speech_v1 as speech

import time

from contextlib import contextmanager
import SparkApi
# 初始化Google Cloud Speech客户端
from google.oauth2 import service_account
app = Flask(__name__)
CORS(app)

#以下密钥信息从控制台获取
appid = ""     #填写控制台中获取的 APPID 信息
api_secret = ""   #填写控制台中获取的 APISecret 信息
api_key =""    #填写控制台中获取的 APIKey 信息

#用于配置大模型版本，默认“general/generalv2”
domain = "generalv3"    # v3.0版本
#云端环境的服务地址
Spark_url = "ws://spark-api.xf-yun.com/v3.1/chat"  


# 录音配置
# fs = 44100  # Sample rate
fs = 16000  # Sample rate 16000既能捕捉到人声的细节，又不会过度占用带宽。
device = 2  # 设备ID for AirPods 3 as input device
channels = 1  # AirPods 3 supports 1 input channel
recording = []  # 初始化为空列表，用于存储录音数据
stream = None  # 初始化录音流为空
recording_count = 0  # 初始化录音计数

# 初始化Google Cloud Speech客户端
# client = speech.SpeechClient()

credentials = service_account.Credentials.from_service_account_file('google_secretkey/service-account-file.json')
client = speech.SpeechClient(credentials=credentials)

text =[]
# length = 0

def getText(role,content):
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



def callback(indata, frames, time, status):
    """此回调函数用于动态捕获录音数据"""
    global recording
    recording.extend(indata.copy())

@app.route('/')
def index():
    return app.send_static_file('front.html')


@app.route('/start-recording', methods=['POST'])
def start_recording():
    global recording, stream
    recording = []  # 重置录音数据列表
    stream = sd.InputStream(samplerate=fs, channels=channels, device=device, callback=callback)
    stream.start()
    return jsonify({"message": "Recording started"})

# 初始化一个全局变量来标记是否是第一次执行
is_first_execution = True




@app.route('/stop-recording', methods=['POST'])
def stop_recording():
    global recording, stream, recording_count, is_first_execution
    stream.stop()
    recording_count += 1
    filename = f"recording_{recording_count}.mp3"
    # filename = f"recording_{recording_count}.pcm"
    # filename = f"recording_saved.mp3"   # 第一步
    # filename = f"recording_3.wav"  # 第二步
    sf.write(filename, np.array(recording), fs)
    audio_file = None
    with timing("\n读取音频文件执行时间"):
        # 读取文件内容到audio_file中
        with open(filename, 'rb') as f:
            audio_file = f.read()
        recording = []  # Reset the recording list after saving
        print(f'Recording stopped and saved, filename: {filename}')
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
            # prompt = "\n请分析下面的英文段落是否有语法错误，并按照以下结构化步骤操作：首先，如果没有检测到语法错误，请表扬用户并表示准备接收下一次输入；其次，如果存在语法错误，请列出每个错误，并跟随一个用引号包裹的简短中文解释，最后给出三个与识别出的错误相关的填空练习题以帮助加强正确用法，附上练习题正确答案。确保所有指示部分都以支持性和教育性的语调呈现。\n "
            prompt = "\n我们即将开启一个主题对话，旨在深入探讨一个特定领域的知识或问题。为了确保我们的交流既丰富又有洞见，请遵循以下指南：每次回复请使用英文，并确保每次回复至少包含40个单词，以便充分表达和探索观点。接下来开始对话。\n"
            Input = prompt + transcript
            # Input = transcript
            # 将is_first_execution设置为False，表示函数已被执行过一次
            is_first_execution = False
        else:
            Input = transcript
        # prompt = "\n请分析下面的英文段落是否有语法错误，并按照以下结构化步骤操作：首先，如果没有检测到语法错误，请表扬用户并表示准备接收下一次输入；其次，如果存在语法错误，请列出每个错误，并跟随一个用引号包裹的简短中文解释，最后给出三个与识别出的错误相关的填空练习题以帮助加强正确用法，附上练习题正确答案。确保所有指示部分都以支持性和教育性的语调呈现。\n "
        # Input = prompt + transcript
        # Input = "\n我: 请分析下面的英文段落是否有语法错误，并按照以下结构化步骤操作：首先，如果没有检测到语法错误，请表扬用户并表示准备接收下一次输入；其次，如果存在语法错误，请列出每个错误，并跟随一个用引号包裹的简短中文解释，最后给出三个与识别出的错误相关的填空练习题以帮助加强正确用法，附上练习题正确答案。确保所有指示部分都以支持性和教育性的语调呈现。\n " + transcript
        print("Input: ",Input)
        question = checklen(getText("user",Input))
        SparkApi.answer =""
        print("AI纠错结果:",end = "")
        SparkApi.main(appid,api_key,api_secret,Spark_url,domain,question)


    return jsonify({"message": "Recording stopped and saved", "filename": filename,
                    "transcript": transcript,
                    'assistant': SparkApi.answer})



if __name__ == '__main__':
    app.run(debug=True,port=5001)


