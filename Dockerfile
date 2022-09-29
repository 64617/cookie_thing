FROM ubuntu:20.04
RUN mkdir /app

ENV TZ=Etc/GMT
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get update && apt-get install -y git python3.8 python3-pip curl
RUN python3.8 -m pip install flask uwsgi tqdm
RUN python3.8 -m pip install psycopg[binary]
RUN apt install -y uwsgi-plugin-python3

WORKDIR /app
COPY app /app
#EXPOSE 9191

CMD ["uwsgi", "--ini", "uwsgi.ini"]
