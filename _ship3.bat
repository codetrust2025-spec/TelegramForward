@echo off
cd /d c:\Users\codet\OneDrive\Desktop\Teleautomation_prod\TelegramForward\dashboard
call npm run build
cd /d c:\Users\codet\OneDrive\Desktop\Teleautomation_prod\TelegramForward
"C:\Program Files\Git\bin\git.exe" add -A
"C:\Program Files\Git\bin\git.exe" commit -m "feat: resume upload shows AI extraction banner with profile data"
"C:\Program Files\Git\bin\git.exe" push origin main
python -c "import socket,paramiko,os;sock=socket.create_connection(('187.127.169.159',22),30);c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect('187.127.169.159',username='root',password='REMOVED_VPS_PASSWORD',sock=sock);sftp=c.open_sftp();sd='static';[sftp.put(os.path.join(dp,f),'/opt/telegramforward.old/static/'+os.path.relpath(os.path.join(dp,f),sd).replace(chr(92),'/')) for dp,dn,fns in os.walk(sd) for f in fns];print('Static deployed');sftp.close();_,so,_=c.exec_command('pm2 restart telegram-backend',timeout=60);print(so.read().decode());c.close();print('DONE')"
