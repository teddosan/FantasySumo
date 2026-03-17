## Local Setup

### 1. Install dependencies:
```bash
pip install nicegui bcrypt requests python-dotenv
```
or
```bash
pip install -r requirements.txt
```

### 2. Add users. This creates `.env` and generates `SECRET_KEY` automatically:
```bash
python auth.py
```

### 3. Run the app:
```bash
python main.py
```
---

## Deploying to Railway

### Prerequisites
- A [Railway](https://railway.app) account
- The Railway CLI installed: `npm install -g @railway/cli`
- Your code in a git repository

### 1. Login
```bash
railway login
```

### 2. Create a new project
```bash
railway init
```

### 3. Add a volume for the database
In the Railway dashboard:
- Go to your service
- Click **Volumes**
- Add a volume mounted at `/data`

### 4. Set environment variables
Generate the secret key with
```
python -c "import secrets; print(secrets.token_hex(32))"
```
then,

In the Railway dashboard, go to **Variables** and add:
```
SECRET_KEY=<generated with: python -c "import secrets; print(secrets.token_hex(32))">
DB_PATH=/data/sumo.db
```

Railway sets `PORT` automatically, do not add it yourself.

### 5. Add users
```bash
railway run python auth.py
```

### 6. Deploy
```bash
railway up
```

Railway will detect `requirements.txt` and `Procfile` automatically.

---

## Common Tasks

Redeploy after a code change:
```bash
railway up
```

View logs:
```bash
railway logs
```

Update a user password:
```bash
railway run python auth.py
```
