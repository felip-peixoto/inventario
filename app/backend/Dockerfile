FROM python:3.13-slim

WORKDIR /repo/app/backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Em dev o código entra por bind mount; a cópia mantém a imagem utilizável standalone.
COPY . /repo/app/backend

# Mantido vivo para `docker compose run` sobrescrever com o comando desejado.
CMD ["sleep", "infinity"]
