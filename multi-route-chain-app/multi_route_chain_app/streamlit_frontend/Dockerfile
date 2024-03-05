# syntax=docker/dockerfile:1.4
FROM amazonlinux:2023

# Install pre-reqs
RUN yum update -y && yum install shadow-utils cmake g++ gcc python3 python3-pip -y
RUN pip3 --version

# Create the user
ARG USERNAME=ec2-user
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME
RUN useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

WORKDIR /app

# # Install AWS CLI
# RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
# RUN unzip awscliv2.zip
# RUN ./aws/install
# RUN aws --version

# Copy files
COPY assets /app/assets
COPY requirements.txt /app
COPY routing_chain_claude.py /app
COPY sqldatabasechain.py /app

RUN pip3 install -r requirements.txt

RUN chown $USERNAME:$USERNAME /app

USER $USER

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "routing_chain_claude_with_memory.py", "--server.port=8501", "--server.address=0.0.0.0"]
