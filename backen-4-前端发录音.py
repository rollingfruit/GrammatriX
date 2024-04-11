from flask import Flask, jsonify
from flask_cors import CORS
import sounddevice as sd
import soundfile as sf
import numpy as np
from flask import Flask, request, jsonify
import os
from google.cloud import speech_v1 as speech
import requests
import time
import io
from contextlib import contextmanager
import SparkApi
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
channels = 1  # 单声道
# recording = []  # 初始化为空列表，用于存储录音数据
stream = None  # 初始化录音流为空
recording_count = 0  # 初始化录音计数

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


# @app.route('/start-recording', methods=['POST'])
# def start_recording():
#     global recording, stream
#     recording = []  # 重置录音数据列表
#     # 创建音频输入流
#     stream = sd.InputStream(samplerate=fs, channels=channels, device=device, callback=callback)
#     stream.start()  # 开始录制
#     return jsonify({"message": "Recording started"})

# 初始化一个全局变量来标记是否是第一次执行
is_first_execution = True
prompt1 = "\n请分析下面的英文段落是否有语法错误，并按照以下结构化步骤操作：首先，如果没有检测到语法错误，请表扬用户并表示准备接收下一次输入；其次，如果存在语法错误，请列出每个错误，并跟随一个用引号包裹的简短中文解释，最后给出三个与识别出的错误相关的填空练习题以帮助加强正确用法，附上练习题正确答案。确保所有指示部分都以支持性和教育性的语调呈现。\n "
prompt2 = "\nYou are an AI conversant specializing in comprehensive discussions within specified domains. Our goal is to engage in a thematic dialogue focused on a particular area of interest. To ensure our conversation is both enriching and insightful, adhere to the following guidelines: Respond in English, and ensure each reply comprises at least 40 words to thoroughly express and explore ideas. Begin your responses by sharing your thoughts or feelings on the subject, followed by a relevant question to facilitate further discussion. Let's commence our dialogue.\n"
        
current_prompt = prompt2
from p2text import process_audio_file


totle_transcript = ""
request_count = 0  # 添加一个全局计数器

@app.route('/toggle-prompt', methods=['POST'])
def toggle_prompt():
    global current_prompt, is_first_execution, request_count, totle_transcript
    
    request_count += 1  # 每次请求时，计数器加1


    if request_count % 2 != 0:  # 奇数次请求
        current_prompt = prompt1
    else:  # 偶数次请求
        current_prompt = prompt2
    is_first_execution = True  # 重置执行状态


    # 基于请求次数的奇偶性来切换Prompt，并调用AI分析接口（如果需要）
    if request_count % 2 != 0:  # 奇数次请求（请求切换为‘语法纠错’）
        # 这里模拟了一个请求体，根据你的实际需求进行调整
        demo_transcript = {"transcript": current_prompt + totle_transcript}
        print(f'ai完整请求：{demo_transcript}')
        totle_transcript = "" # 重置totle_transcript
        # 调用/ai-analysis接口并获取ai_analysis_response
        ai_analysis_response = requests.post('http://localhost:5001/ai-analysis', json=demo_transcript)
        if ai_analysis_response.ok:  # 检查响应是否成功
            try:
                ai_response_data = ai_analysis_response.json()  # 尝试解析 JSON
                assistant_response = ai_response_data.get('assistant')
                return jsonify({"message": "请对我的口语进行纠错并提供相关练习", "currentPrompt": current_prompt, "assistant": assistant_response})
            except ValueError:  # 捕获 JSON 解析错误
                return jsonify({"error": "AI分析接口没有返回有效的JSON"})
        else:
            return jsonify({"error": "AI分析接口调用失败"})
    else: # 偶数次请求（请求切换为对话）
        return jsonify({"message": "Prompt2已切换，无AI分析", "currentPrompt": current_prompt})

# @app.route('/stop-recording', methods=['POST'])
@app.route('/upload-audio', methods=['POST'])
def stop_recording():
    # global recording, stream, recording_count, is_first_execution, current_prompt, totle_transcript
    global stream, recording_count, is_first_execution, current_prompt, totle_transcript
    
    if 'audioData' not in request.files:
        return "No audio data received.", 400
    
    audio_file = request.files['audioData']
    # stream.stop()  # 停止录制
    recording_count += 1

    # 读取音频数据并转换为所需格式（这里假设上传的是wav格式的音频）
    data, samplerate = sf.read(io.BytesIO(audio_file.read()), dtype='int16')
    
    # 修改文件名和格式为WAV，因为我们要保存为PCM格式
    filename = f"recording_{recording_count}.wav"
    
    # 使用PCM 16位保存音频文件
    sf.write(filename, data, samplerate, subtype='PCM_16')
    audio_file = None
    with timing("\n读取音频文件执行时间"):
        # 读取文件内容到audio_file中
        with open(filename, 'rb') as f:
            audio_file = f.read()
        # recording = []  # Reset the recording list after saving
    with timing("\n语音识别执行时间"):

        # 调用函数并传递参数
        transcript = process_audio_file(filename)
        totle_transcript += transcript
        # 获取识别结果
        print(f'Transcript: {transcript}')
    # 调用AI分析接口进行处理
    ai_analysis_response = requests.post('http://localhost:5001/ai-analysis', json={"transcript": transcript})
    
    return jsonify({"message": "Recording stopped, saved, and sent for AI analysis", 
                    "filename": filename, 
                    "transcript": transcript, 
                    "assistant": ai_analysis_response.json().get('assistant')})


@app.route('/ai-analysis', methods=['POST'])
def ai_analysis():
    global is_first_execution, current_prompt
    data = request.get_json()
    transcript = data.get('transcript', '')

    print(f'is_first_execution: {is_first_execution}')
    Input = current_prompt + transcript if is_first_execution else transcript
    is_first_execution = False  # 更新执行状态
    
    print("Input for AI analysis: ", Input)
    question = checklen(getText("user", Input))
    SparkApi.answer = ""
    SparkApi.main(appid, api_key, api_secret, Spark_url, domain, question)

    return jsonify({"message": "AI analysis completed", "input": Input, "assistant": SparkApi.answer})



if __name__ == '__main__':
    app.run(debug=True,port=5001)


