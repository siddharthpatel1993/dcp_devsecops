FROM python:3.9
ENV DEBBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV OPENAI_API_KEY='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'
RUN apt-get update
RUN apt-get install -y git python3 python3-pip
RUN python3 -m pip install --upgrade pip
WORKDIR /home
ADD . .
RUN python3 -m pip install -r requirements.txt
RUN mkdir /var/log/gunicorn /var/run/gunicorn
EXPOSE 8000
ENTRYPOINT gunicorn --bind 0.0.0.0:8000 --workers 3 --access-logfile /var/log/gunicorn/access.log --error-logfile /var/log/gunicorn/error.log LearnEasyAI.wsgi

