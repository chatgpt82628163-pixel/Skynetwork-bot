# SkyNetwork Discord bot

Verifies Discord members through SkyNetwork Connect: a member presses the button, signs in on the
SkyNetwork website and gets the nickname "First Last - CID" (and, optionally, a role).

## Install (Ubuntu/Debian server)

```
sudo git clone https://github.com/Anntixs/skynetwork_bot /opt/skynetwork-bot
cd /opt/skynetwork-bot
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt
sudo cp .env.example /etc/skynetwork-bot.env
sudo nano /etc/skynetwork-bot.env        # fill in the token and the Connect client
sudo chmod 600 /etc/skynetwork-bot.env
sudo chown -R www-data /opt/skynetwork-bot
sudo cp skynetwork-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now skynetwork-bot
```

The Connect client is created on the website (Staff → Connect) with the redirect address
`PUBLIC_URL/callback`, e.g. `https://sky.network.npzy2.us/discord/callback`.

nginx forwards `PUBLIC_URL` to the bot:

```
location /discord/ {
    proxy_pass http://127.0.0.1:8090/;
}
```

The bot needs the Manage Nicknames and Manage Roles permissions, and its role must be above the
members' roles. Post the button with `/setup_verify`.

## Update

```
cd /opt/skynetwork-bot && sudo git pull && sudo systemctl restart skynetwork-bot
```
