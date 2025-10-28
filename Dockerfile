FROM python:3.13

WORKDIR /usr/src/app
COPY . ./

RUN [ "sed", "-i", "s/password=self.password)/password=self.password, known_hosts=None)/", "src/kalissh.py"]

RUN pip3 install -e .
RUN pip3 install jinja2

ENV OPENAI_API_KEY=''
ENV TARGET_USERNAME=root
ENV TARGET_PASSWORD=kali
ENV TARGET_HOST=192.168.56.100

RUN mkdir /root/.ssh/
# RUN ssh-keyscan $TARGET_HOST >> ~/.ssh/known_hosts

CMD ["python", "./src/cochise.py" ]
