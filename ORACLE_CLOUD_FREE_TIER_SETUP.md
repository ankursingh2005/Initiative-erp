# Oracle Cloud Free Tier Deployment

This project can run on an Oracle Cloud Free Tier Ubuntu VM.

## Recommended Setup

- Compute: `VM.Standard.E2.1.Micro` or any always-free Ubuntu instance
- OS: Ubuntu 22.04
- App server: `uvicorn` with `systemd`
- Reverse proxy: `nginx`
- Database:
  - Small usage: keep SQLite on the VM
  - Better production setup: run PostgreSQL on the same VM and set `DATABASE_URL`

## 1. Open Required Ports

In Oracle Cloud, allow:

- `22` for SSH
- `80` for HTTP
- `443` for HTTPS

Also allow the same ports in the VM firewall if enabled.

## 2. Connect to the VM

```bash
ssh -i your-key.pem ubuntu@your-vm-public-ip
```

## 3. Install System Packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx git
```

## 4. Upload or Clone the Project

```bash
git clone <your-repository-url> idspl
cd idspl
```

## 5. Create the Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 6. Set Production Environment Variables

Create `/etc/idspl.env`:

```bash
sudo nano /etc/idspl.env
```

Example:

```env
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///./scheme_erp.db
```

If you install PostgreSQL on the VM, use a URL like:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/idspl
```

## 7. Install the Systemd Service

Copy [deploy/oracle/idspl.service](deploy/oracle/idspl.service) to `/etc/systemd/system/idspl.service` and update `WorkingDirectory` if needed.

```bash
sudo cp deploy/oracle/idspl.service /etc/systemd/system/idspl.service
sudo systemctl daemon-reload
sudo systemctl enable idspl
sudo systemctl start idspl
sudo systemctl status idspl
```

## 8. Configure Nginx

Copy [deploy/oracle/idspl.nginx.conf](deploy/oracle/idspl.nginx.conf) to `/etc/nginx/sites-available/idspl`.

```bash
sudo cp deploy/oracle/idspl.nginx.conf /etc/nginx/sites-available/idspl
sudo ln -s /etc/nginx/sites-available/idspl /etc/nginx/sites-enabled/idspl
sudo nginx -t
sudo systemctl restart nginx
```

Edit `server_name` in the nginx file to your domain or public IP.

## 9. Optional HTTPS

If you have a domain:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## 10. Update the App

```bash
cd ~/idspl
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart idspl
```

## Notes

- SQLite is acceptable for a small internal deployment on a single Oracle VM.
- For multiple users and better reliability, move to PostgreSQL.
- Keep `SECRET_KEY` private and never commit it to the repository.