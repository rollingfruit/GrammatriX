# 使用官方Python镜像
FROM python:3.8

# 设置工作目录为/app
WORKDIR /app

# 将当前目录下的所有文件复制到容器的/app目录下
COPY . /app

# 安装requirements.txt中列出的所有依赖
RUN pip install --no-cache-dir -r requirements.txt

# 使5000端口可用于其他容器
EXPOSE 5000

# 定义环境变量
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 运行Flask应用
CMD ["flask", "run"]
