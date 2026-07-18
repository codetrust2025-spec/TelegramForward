#!/usr/bin/env python3
"""Install Ollama directly on the VPS and pull required models."""
import paramiko
import time

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, timeout: int = 600) -> tuple[str, str, int]:
    """Execute SSH command."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err, exit_code
    finally:
        client.close()

def main():
    print("=== Install Ollama on VPS ===\n")
    
    print("[1/6] Checking if Ollama is already installed...")
    out, err, code = ssh_command("which ollama")
    if code == 0 and out.strip():
        print(f"  ✓ Ollama already installed at: {out.strip()}")
    else:
        print("  Installing Ollama...")
        out, err, code = ssh_command("curl -fsSL https://ollama.com/install.sh | sh", timeout=300)
        if code == 0:
            print("  ✓ Ollama installed successfully")
        else:
            print(f"  ✗ Installation failed: {err}")
            return
    
    print("\n[2/6] Starting Ollama service...")
    ssh_command("systemctl enable ollama", timeout=30)
    ssh_command("systemctl start ollama", timeout=30)
    time.sleep(3)
    out, err, code = ssh_command("systemctl status ollama | head -10")
    if 'active (running)' in out:
        print("  ✓ Ollama service is running")
    else:
        print("  Status:")
        print(out)
    
    print("\n[3/6] Pulling primary model (qwen2.5:7b)...")
    print("  (This may take 5-10 minutes...)")
    out, err, code = ssh_command("ollama pull qwen2.5:7b", timeout=900)
    if code == 0:
        print("  ✓ qwen2.5:7b pulled successfully")
    else:
        print(f"  ✗ Failed to pull qwen2.5:7b")
    
    print("\n[4/6] Pulling fallback model (gemma2:2b)...")
    out, err, code = ssh_command("ollama pull gemma2:2b", timeout=600)
    if code == 0:
        print("  ✓ gemma2:2b pulled successfully")
    else:
        print(f"  ✗ Failed to pull gemma2:2b")
    
    print("\n[5/6] Updating .env to use local Ollama...")
    ssh_command(f"""cd {VPS_PATH} && sed -i 's/OLLAMA_EXPECT_REVERSE_SSH_TUNNEL=true/OLLAMA_EXPECT_REVERSE_SSH_TUNNEL=false/' .env""")
    print("  ✓ Updated OLLAMA_EXPECT_REVERSE_SSH_TUNNEL=false")
    
    print("\n[6/6] Restarting backend...")
    ssh_command("pm2 restart telegram-backend")
    print("  ✓ Backend restarted")
    
    time.sleep(3)
    
    print("\n=== Testing Ollama ===")
    out, err, code = ssh_command('curl -s http://localhost:11434/api/tags | head -20')
    if code == 0 and '"models"' in out:
        print("  ✓ Ollama is accessible")
        print(out[:300])
    else:
        print("  ✗ Ollama not responding")
    
    print("\n=== Installation Complete ===")
    print("Ollama is now running on the VPS")
    print("Refresh your dashboard and the AI should be working")

if __name__ == '__main__':
    main()
