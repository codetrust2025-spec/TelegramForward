# Deployment Guide — Telegram Forwarder

## Recommended: Hostinger VPS (~$4/month)

---

## Step 1 — Buy a VPS

1. Go to https://hostinger.com/vps-hosting
2. Choose **KVM 1** plan (~$4/month)
3. Select **Ubuntu 22.04** as OS
4. Choose any datacenter (Singapore is closest for India)
5. Complete purchase — you'll get an IP address + root password via email

---

## Step 2 — Connect to your VPS

Open PowerShell on your Windows machine:

```
ssh root@YOUR_VPS_IP
```

Enter the root password from the email.

---

## Step 3 — Upload your project files

On your Windows machine, open a new PowerShell window:

```powershell
# Install scp if needed, then upload
scp -r "C:\Users\ravin\Desktop\TelegramForward" root@YOUR_VPS_IP:/opt/telegramforward
```

Or use **FileZilla** (free FTP client):
- Host: YOUR_VPS_IP
- Username: root
- Password: your VPS password
- Port: 22
- Upload the entire TelegramForward folder to /opt/telegramforward

---

## Step 4 — Run the deployment script

Back in your SSH terminal:

```bash
cd /opt/telegramforward
bash deploy.sh
```

This will:
- Install Python, Node.js, Nginx
- Build the React dashboard
- Start the backend with PM2 (auto-restart on crash/reboot)
- Configure Nginx as reverse proxy

---

## Step 5 — Open the dashboard

Open your browser and go to:
```
http://YOUR_VPS_IP
```

You'll see the Telegram Forwarder dashboard.

---

## Step 6 — Log in your Telegram accounts

1. Click **+ Login** on Account 1
2. Select your phone number from the dropdown
3. Enter the OTP sent to your Telegram app
4. Repeat for Account 2

The session files are saved on the VPS and persist forever (even after restarts).

---

## Step 7 — Upload your groups list

1. Click **📂 GROUPS LIST** in the dashboard
2. Upload your Excel/CSV file
3. Click **Apply**

---

## Step 8 — Start forwarding

Click **▶ Start Auto (rotation)** — it runs 24/7 automatically.

---

## Useful Commands (run on VPS via SSH)

```bash
# View live logs
pm2 logs telegramforward

# Restart server
pm2 restart telegramforward

# Stop server
pm2 stop telegramforward

# Check status
pm2 status

# Update code after changes
cd /opt/telegramforward
git pull   # if using git, or re-upload files
cd dashboard && npm run build && cd ..
pm2 restart telegramforward
```

---

## Updating the project later

1. Make changes on your Windows machine
2. Re-upload changed files via scp or FileZilla
3. If you changed the frontend: `cd /opt/telegramforward/dashboard && npm run build`
4. Restart: `pm2 restart telegramforward`

---

## Important Notes

- **Session files** (`.session`) are stored on the VPS — never delete them or you'll need to re-login
- **groups_list.json** persists on the VPS — your cleaned group list is safe
- **custom_message.txt** persists — your message is saved
- The server auto-restarts if it crashes (PM2 handles this)
- The server auto-starts on VPS reboot (PM2 startup handles this)

---

## Firewall (optional but recommended)

```bash
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS (if you add SSL later)
ufw enable
```

---

## Free SSL with Let's Encrypt (optional)

If you have a domain name pointed to your VPS IP:

```bash
apt install certbot python3-certbot-nginx -y
certbot --nginx -d yourdomain.com
```

This gives you `https://yourdomain.com` with auto-renewing SSL.
