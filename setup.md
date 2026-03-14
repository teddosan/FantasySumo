# Fantasy Sumo League
---

## Files
- main.py           the app
- auth.py           login, sessions, rate limiting
- config.py         reads environment variables
- requirements.txt  python dependencies
- Procfile          tells hosting services how to start the app
- .env              your local secrets (never commit this)
- .env.example      shows what variables are expected (safe to commit)
- .gitignore        keeps secrets out of git
---

## Local Setup
**Install dependencies**
pip install -r requirements.txt

**Set passwords**
Run `python auth.py` once. It asks for each player's password interactively,
hashes them with bcrypt, and writes everything to `.env`.

**Run the app**
python main.py

Visit `http://localhost:8080`.

To reset or change a password, just run `python auth.py` again.

---

## Hosting
**1. SSH in**

```bash
ssh root@your-server-ip
```

**2. Install Python**

```bash
apt update && apt install python3 python3-pip -y
pip3 install nicegui bcrypt requests python-dotenv
```

**3. Copy your files up** (run locally)

```bash
scp main.py auth.py config.py requirements.txt root@your-server-ip:/app/
```

**4. Set up passwords**

```bash
cd /app
python3 auth.py
```

This writes `.env` on the server with your hashed passwords.

**5. Test it**

```bash
python3 main.py
```

Visit `http://your-server-ip:8080` to confirm it works, then Ctrl+C.

**6. Install Caddy for HTTPS**

Caddy handles SSL certificates automatically via Let's Encrypt.

```bash
apt install caddy -y
```

Edit `/etc/caddy/Caddyfile`:

```
sumo.yourdomain.com {
    reverse_proxy localhost:8080
}
```

```bash
systemctl restart caddy
```

Your app is now live at `https://sumo.yourdomain.com`.

**7. Keep it running with systemd**

Create `/etc/systemd/system/sumo.service`:

```ini
[Unit]
Description=Fantasy Sumo League
After=network.target

[Service]
WorkingDirectory=/app
ExecStart=python3 main.py
Restart=always
User=root
EnvironmentFile=/app/.env

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable sumo
systemctl start sumo
```

The app now starts on boot and restarts automatically if it crashes.

**Useful commands**

```bash
systemctl status sumo        # is it running?
journalctl -u sumo -f        # live logs
systemctl restart sumo       # restart after a code update
```

**Deploying an update**

```bash
scp main.py auth.py config.py root@your-server-ip:/app/
ssh root@your-server-ip systemctl restart sumo
```

---

## Hosting on Railway

Railway is the easiest option if you want zero server management.

**1. Install the Railway CLI**

```bash
npm install -g @railway/cli
railway login
```

**2. Set up passwords locally first**

```bash
python auth.py
```

This writes your `AUTH_CONFIG` value to `.env`. Copy the printed line
that starts with `AUTH_CONFIG=`.

**3. Deploy**

```bash
railway init
railway up
```

**4. Add environment variables**

In the Railway dashboard, go to your service, then Variables, and add:

```
AUTH_CONFIG=<paste the value from step 2>
DB_PATH=/data/sumo.db
```

Railway injects `PORT` automatically so you do not need to set it.

**5. Add a volume for the database**

In the Railway dashboard, go to Volumes and add a volume mounted at `/data`.
This keeps your draft data across deploys.

---

## Notes

- Passwords are bcrypt-hashed (work factor 12). Plaintext passwords are
  never stored anywhere.
- Sessions are random 256-bit tokens stored server-side in SQLite.
  The browser only ever sees the token.
- Five failed login attempts from the same IP triggers a 15-minute lockout.
- `.env` and `sumo.db` are in `.gitignore`. Do not commit them.
