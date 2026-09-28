<div align="center">
  <img src="docs/logo.png" width="96" alt="SkyNetwork">
  <h1>Skynetwork-bot</h1>
  <p>Discord-бот SkyNetwork — верификация участников через SkyNetwork Connect</p>

  [![CI](https://github.com/chatgpt82628163-pixel/Skynetwork-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/chatgpt82628163-pixel/Skynetwork-bot/actions/workflows/ci.yml)

  [Сайт](https://sky.network.npzy2.us) · [Поддержка](https://sky.network.npzy2.us/support)
</div>

---

## Что это

Skynetwork-bot связывает аккаунты Discord с аккаунтами SkyNetwork.
Участник нажимает кнопку в Discord, входит на сайте SkyNetwork своим CID и паролем — пароль до бота не доходит.
После подтверждения бот устанавливает ник «Имя Фамилия — CID» и, по желанию, выдаёт роль.
Один CID может быть привязан только к одному Discord-аккаунту.

## Возможности

**Верификация**
- Кнопка «Verify» с OAuth 2.0 + PKCE — ссылка одноразовая, действует 10 минут.
- Ник устанавливается автоматически: «Имя Фамилия — CID» (до 32 символов).
- Роль выдаётся сразу после верификации (настраивается через `VERIFIED_ROLE_ID`).
- Если CID перешёл к другому Discord-аккаунту, у предыдущего ник и роль снимаются.

**Слэш-команды**
- `/setup_verify` — размещает кнопку верификации в текущем канале (только для администраторов сервера).

**Малая веб-страница**
- Принимает OAuth-колбэк от сайта и показывает участнику результат верификации.
- Роут `/health` для мониторинга.
- Подключается к nginx через `location /discord/`.

**Хранилище**
- SQLite-база (`links.db`) хранит связи CID ↔ Discord-ID по гильдиям.

## Скриншоты

> Страница сайта — раздел «Кто в эфире»

![Онлайн на карте](https://raw.githubusercontent.com/chatgpt82628163-pixel/Skynetwork-bot/main/docs/logo.png)

<!-- Для скриншотов сайта используйте readme-assets/online.png, home-dark.png и т.д. -->

## Сборка и запуск

**Требования:** Python 3.11+, `discord.py >= 2.3`, `aiohttp >= 3.9`.

```bash
git clone https://github.com/chatgpt82628163-pixel/Skynetwork-bot
cd Skynetwork-bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env   # заполнить — см. ниже
python3 bot.py
```

**Переменные окружения** (`.env` или `/etc/skynetwork-bot.env` на сервере):

| Переменная | Описание |
|---|---|
| `DISCORD_TOKEN` | Токен бота из Discord Developer Portal |
| `CONNECT_CLIENT_ID` | Client ID приложения SkyNetwork Connect (Staff → Connect) |
| `CONNECT_CLIENT_SECRET` | Секрет того же приложения |
| `SKYNET_URL` | Адрес сайта, например `https://sky.network.npzy2.us` |
| `PUBLIC_URL` | Внешний адрес бота, например `https://sky.network.npzy2.us/discord` |
| `BOT_WEB_PORT` | Локальный порт веб-страницы (по умолчанию `8090`) |
| `VERIFIED_ROLE_ID` | ID роли для верифицированных (необязательно) |
| `BOT_DB` | Путь к базе SQLite (по умолчанию `links.db` рядом с `bot.py`) |

Redirect URI клиента Connect: `PUBLIC_URL/callback`, например `https://sky.network.npzy2.us/discord/callback`.

**nginx:**

```nginx
location /discord/ {
    proxy_pass http://127.0.0.1:8090/;
}
```

**Бот нуждается** в правах Manage Nicknames и Manage Roles; его роль должна быть выше ролей участников.

После запуска разместите кнопку верификации командой `/setup_verify`.

**Установка как systemd-сервис (Ubuntu/Debian):**

```bash
sudo git clone https://github.com/chatgpt82628163-pixel/Skynetwork-bot /opt/skynetwork-bot
cd /opt/skynetwork-bot
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt
sudo cp .env.example /etc/skynetwork-bot.env
sudo nano /etc/skynetwork-bot.env
sudo chmod 600 /etc/skynetwork-bot.env
sudo chown -R www-data /opt/skynetwork-bot
sudo cp skynetwork-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now skynetwork-bot
```

**Обновление:**

```bash
cd /opt/skynetwork-bot && sudo git pull && sudo systemctl restart skynetwork-bot
```

## Устройство

```
Skynetwork-bot/
├── bot.py                  # весь код бота и веб-страницы
├── requirements.txt        # зависимости Python
├── skynetwork-bot.service  # systemd unit
├── .env.example            # шаблон переменных окружения
└── docs/
    └── logo.png            # логотип
```

## Часть SkyNetwork

Skynetwork-bot — один из компонентов платформы SkyNetwork.

| Репозиторий | Описание |
|---|---|
| [SkyNetwork-site](https://github.com/chatgpt82628163-pixel/SkyNetwork-site) | Основной сайт |
| [SkyNetwork-FSD](https://github.com/chatgpt82628163-pixel/SkyNetwork-FSD) | Диспетчерская служба |
| [Network-ATC](https://github.com/chatgpt82628163-pixel/Network-ATC) | Программа для диспетчеров |
| [SkyPilot](https://github.com/chatgpt82628163-pixel/SkyPilot) | Программа для пилотов |
| [Skynetwork-voice](https://github.com/chatgpt82628163-pixel/Skynetwork-voice) | Голосовой сервер |
| [SkyRUS-site](https://github.com/chatgpt82628163-pixel/SkyRUS-site) | Сайт SkyRUS |
| [Skynetwork-bot](https://github.com/chatgpt82628163-pixel/Skynetwork-bot) | Этот репозиторий |

---

## English

**Skynetwork-bot** is the SkyNetwork Discord bot. It links Discord accounts to SkyNetwork accounts via OAuth 2.0 + PKCE: a member clicks **Verify**, signs in on the SkyNetwork website, and the bot sets their nickname to "First Last — CID" and grants the verified role. Passwords never reach the bot. One CID maps to one Discord account per server.

**Features:** persistent verify button, `/setup_verify` admin command, small OAuth callback web page served under `/discord/` via nginx, SQLite storage.

**Run:** Python 3.11+, install `requirements.txt`, set environment variables (see table above), run `python3 bot.py`.

**Links:** [Site](https://sky.network.npzy2.us) · [Support](https://sky.network.npzy2.us/support)
