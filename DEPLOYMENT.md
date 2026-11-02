# FreshDash Backend — Production Deployment & Hosting Guide

This guide details the complete production architecture, deployment instructions, and hosting recommendations for the **FreshDash** Django REST Framework backend using **SQLite3**.

---

## 1. Production Hosting Recommendations for SQLite3

SQLite3 is a fast, file-based relational database that operates inside the application process. Because it relies directly on the local filesystem, **the database file must be stored on persistent disk storage**.

### Recommended Providers

| Provider | Type | Why It's Recommended | Estimated Cost |
|---|---|---|---|
| **Hetzner Cloud** (CX22 / CPX11) | VPS / Cloud Compute | Exceptional NVMe SSD I/O performance, persistent disk included, reliable European/US data centers. | €3.50 – €5.00/mo |
| **DigitalOcean** (Basic Droplet) | VPS / Cloud Compute | 1 GB / 25 GB NVMe persistent disk, easy snapshots, global availability (Bangalore, Frankfurt, NYC, etc.). | \$6.00/mo |
| **AWS Lightsail / EC2** | VPS / Cloud Compute | Persistent Amazon EBS volume, simple firewall, easy VPC integration. | \$3.50 – \$5.00/mo |
| **Render** (Web Service + Disk) | PaaS | Automated Git deployments, supports mounting a **Persistent Disk** (e.g. `/data`) to keep SQLite safe across deploys. | \$7.00/mo (Instance) + \$0.25/GB disk |
| **Fly.io** | Containers | Multi-region, supports `fly volumes` mount to persist `/data/db.sqlite3`. | \$3.00 – \$5.00/mo |

> [!CAUTION]
> **Ephemeral Container Warning:** Never run SQLite on serverless containers without persistent disk (e.g., standard Heroku, Vercel Serverless, or default AWS Fargate/ECS without EFS). Every deployment or container restart on ephemeral filesystems resets the database to its build image. Always mount a persistent volume (e.g. `/data`).

---

## 2. Production Architecture

```
[ Mobile App (FreshDash) ]
           │  HTTPS
           ▼
[ Reverse Proxy (Nginx / Caddy / Cloudflare) ]
           │  Port 8000
           ▼
[ Gunicorn WSGI (2 Workers, 4 Threads per worker) ]
           │
           ├─► WhiteNoise (Static Files: /static/ -> compressed & hashed)
           │
           ├─► Persistent Disk Volume (/data)
           │      ├─► db.sqlite3 (WAL Mode + busy_timeout=10000)
           │      ├─► db.sqlite3-wal (Write-Ahead Log)
           │      └─► media/ (User uploads, avatars, receipts)
           │
           └─► Automated Daily Backup (Python online backup API -> /data/backups/)
```

---

## 3. Deployment Option A: Docker Compose (Recommended)

### Step 1: Clone Repository & Configure Environment
```bash
git clone <your-repo-url> freshdash-backend
cd freshdash-backend

cp .env.example .env
nano .env
```
Ensure you set:
- `DEBUG=False`
- `SECRET_KEY=<long-random-string>`
- `JWT_SECRET_KEY=<different-long-random-string>`
- `ALLOWED_HOSTS=api.yourdomain.com`
- `CORS_ALLOWED_ORIGINS=https://yourdomain.com`

### Step 2: Build & Start Container
```bash
docker compose up -d --build
```

### Step 3: Verify Running Status
```bash
docker compose ps
docker compose logs -f api
```

### Step 4: Verify Health Endpoint
```bash
curl http://localhost:8000/api/v1/health/
# Expected: {"status": "healthy", "service": "FreshDash Backend API", "version": "1.0.0"}
```

---

## 4. Deployment Option B: Ubuntu Linux VPS (Systemd + Nginx + Gunicorn)

### Step 1: System Packages
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip nginx git
```

### Step 2: Set Up Application
```bash
sudo mkdir -p /var/www/freshdash-backend /data /data/media
sudo chown -R www-data:www-data /var/www/freshdash-backend /data

sudo -u www-data git clone <your-repo-url> /var/www/freshdash-backend
cd /var/www/freshdash-backend

# Create virtual environment
sudo -u www-data python3 -m venv .venv
sudo -u www-data .venv/bin/pip install --upgrade pip
sudo -u www-data .venv/bin/pip install -r requirements.txt

# Configure environment
sudo -u www-data cp .env.example .env
sudo -u www-data nano .env
```
Set `SQLITE_DB_PATH=/data/db.sqlite3` and `MEDIA_ROOT=/data/media`.

### Step 3: Run Initial Migrations & Static Collection
```bash
sudo -u www-data .venv/bin/python manage.py migrate --noinput
sudo -u www-data .venv/bin/python manage.py collectstatic --noinput
```

### Step 4: Configure Systemd Service
```bash
sudo cp freshdash.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable freshdash
sudo systemctl start freshdash
sudo systemctl status freshdash
```

### Step 5: Configure Nginx Reverse Proxy
Create `/etc/nginx/sites-available/freshdash`:
```nginx
server {
    server_name api.yourdomain.com;

    client_max_body_size 20M;

    # Static files served directly by WhiteNoise or Nginx
    location /static/ {
        alias /var/www/freshdash-backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    # Uploaded media files
    location /media/ {
        alias /data/media/;
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
    }

    # API and Django app
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 80;
}
```
Enable site and acquire SSL certificate:
```bash
sudo ln -s /etc/nginx/sites-available/freshdash /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo certbot --nginx -d api.yourdomain.com
```

---

## 5. Automated Database Backups

A custom management command is configured to perform live online backups using Python's non-blocking `sqlite3.backup()` API:

```bash
python manage.py backup_db
```
- Creates timestamped snapshots in `BASE_DIR/backups/`.
- Automatically prunes backups older than 7 days.

### Schedule Daily Backup with Cron
Add this entry to your crontab (`crontab -e`):
```cron
# Run safe database backup every day at 02:00 UTC
0 2 * * * /var/www/freshdash-backend/.venv/bin/python /var/www/freshdash-backend/manage.py backup_db >> /var/www/freshdash-backend/logs/backup.log 2>&1
```

### Restore Database
In the event of accidental data corruption:
```bash
python manage.py restore_db /path/to/backup_file.sqlite3
```
- Performs a `PRAGMA integrity_check` on the backup file.
- Takes an automatic safety snapshot of the active database before replacing it.
- Restores the database file safely.

---

## 6. Post-Deployment Verification Checklist

Run these curl commands against your live production domain to verify operational status:

1. **Health Check:**
   ```bash
   curl -I https://api.yourdomain.com/api/v1/health/
   # Expect: HTTP/2 200 OK
   ```

2. **Security Headers Verification:**
   ```bash
   curl -I https://api.yourdomain.com/api/v1/health/
   # Expect:
   # Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
   # X-Content-Type-Options: nosniff
   # X-Frame-Options: DENY
   ```

3. **Categories & Catalog Browsing:**
   ```bash
   curl https://api.yourdomain.com/api/v1/categories/
   # Expect: List of active produce categories
   ```

4. **Authentication Signup & Login:**
   ```bash
   curl -X POST https://api.yourdomain.com/api/v1/auth/login/ \
        -H "Content-Type: application/json" \
        -d '{"username": "testuser", "password": "Password123!"}'
   # Expect: 200 OK with tokens.access, tokens.refresh
   ```

5. **Token Refresh Rotation:**
   ```bash
   curl -X POST https://api.yourdomain.com/api/v1/auth/token/refresh/ \
        -H "Content-Type: application/json" \
        -d '{"refresh": "<REFRESH_TOKEN>"}'
   # Expect: 200 OK with newly rotated tokens
   ```

6. **Static Files (WhiteNoise):**
   ```bash
   curl -I https://api.yourdomain.com/static/rest_framework/css/bootstrap.min.css
   # Expect: HTTP/2 200 OK
   ```

