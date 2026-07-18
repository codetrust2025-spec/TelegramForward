#!/usr/bin/env python3
"""Pull the qwen2.5-vl vision model."""
import paramiko

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'

def main():
    print("=== Installing qwen2.5-vl Vision Model ===\n")
    print("This is a ~4.4GB download and will take 5-10 minutes...")
    print("Progress will be shown below:\n")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
    
    stdin, stdout, stderr = client.exec_command('ollama pull qwen2.5-vl:7b', timeout=900)
    
    # Stream output in real-time
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line.rstrip())
    
    exit_code = stdout.channel.recv_exit_status()
    
    if exit_code == 0:
        print("\n✓ qwen2.5-vl:7b installed successfully")
    else:
        err = stderr.read().decode()
        print(f"\n✗ Installation failed: {err}")
    
    # List all models
    print("\n=== Installed Models ===")
    stdin, stdout, stderr = client.exec_command('ollama list')
    stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    
    # Restart backend
    print("=== Restarting Backend ===")
    stdin, stdout, stderr = client.exec_command('pm2 restart telegram-backend')
    stdout.channel.recv_exit_status()
    print("✓ Backend restarted")
    
    client.close()
    
    print("\n=== Installation Complete ===")
    print("All required models are now installed!")
    print("Refresh your dashboard to verify Ollama is working.")

if __name__ == '__main__':
    main()
