#!/usr/bin/env python3
"""Check Ollama status and complete configuration."""
import paramiko
import json

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, timeout: int = 60) -> tuple[str, str, int]:
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
    print("=== Checking Ollama Status ===\n")
    
    # Check if Ollama service is running
    print("[1/5] Checking Ollama service...")
    out, err, code = ssh_command("systemctl is-active ollama")
    if 'active' in out:
        print("  ✓ Ollama service is running")
    else:
        print(f"  ✗ Ollama service not active: {out.strip()}")
        print("  Starting service...")
        ssh_command("systemctl start ollama")
    
    # Check API accessibility
    print("\n[2/5] Testing Ollama API...")
    out, err, code = ssh_command('curl -s http://localhost:11434/api/tags')
    if code == 0 and out.strip():
        try:
            data = json.loads(out)
            models = data.get('models', [])
            print(f"  ✓ Ollama API is accessible")
            print(f"  Installed models: {len(models)}")
            for model in models:
                print(f"    - {model.get('name')}")
        except:
            print(f"  Response: {out[:200]}")
    else:
        print("  ✗ Ollama API not responding")
        return
    
    # Check .env configuration
    print("\n[3/5] Checking .env configuration...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && grep OLLAMA_EXPECT_REVERSE_SSH_TUNNEL .env")
    current_value = out.strip().split('=')[-1] if '=' in out else 'not set'
    print(f"  Current: OLLAMA_EXPECT_REVERSE_SSH_TUNNEL={current_value}")
    
    if current_value == 'true':
        print("  Updating to false (using local Ollama)...")
        ssh_command(f"cd {VPS_PATH} && sed -i 's/OLLAMA_EXPECT_REVERSE_SSH_TUNNEL=true/OLLAMA_EXPECT_REVERSE_SSH_TUNNEL=false/' .env")
        print("  ✓ Configuration updated")
    else:
        print("  ✓ Already configured for local Ollama")
    
    # Restart backend
    print("\n[4/5] Restarting backend to apply changes...")
    out, err, code = ssh_command("pm2 restart telegram-backend")
    print("  ✓ Backend restarted")
    
    # Test from backend
    print("\n[5/5] Testing AI from backend...")
    import time
    time.sleep(3)
    out, err, code = ssh_command(f"""cd {VPS_PATH} && venv/bin/python3 -c "
from dotenv import load_dotenv
load_dotenv()
from core.ai_gateway import health
status = health()
print('Status:', status.get('status'))
print('Endpoint reachable:', status.get('endpoint_reachable'))
print('Primary model available:', status.get('model_available'))
print('Models installed:', status.get('models_installed', []))
"
""")
    print(out)
    
    print("\n=== Status Check Complete ===")
    print("Refresh your dashboard - the Ollama error should be gone!")

if __name__ == '__main__':
    main()
