FROM node:20

RUN mkdir -p /app
WORKDIR /app

RUN npm i -g @slidev/cli @slidev/theme-seriph

RUN npm i -g playwright-chromium

RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt \
    apt-get update && npx -y playwright install --with-deps && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "slidev" ]