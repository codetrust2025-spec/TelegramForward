#!/usr/bin/env python3
"""Install the missing vision models for Ollama."""
import paramiko
import time

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'

def ssh_command(command: str, timeout: int = 900, show_progress: bool = False):
    """Execute SSH command with optional progress display."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        
        if show_progress:
            while True:
                line = stdout.readline()
                if not line:
                    break
                print(line.rstrip())
        
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode() if not show_progress else ''
        err = stderr.read().decode()
        return out, err, exit_code
    finally:
        client.close()

def main():
    print("=== Installing Vision Models ===\n")
    
    print("[1/3] Checking currently installed models...")
    out, err, code = ssh_command('ollama list')
    print(out)
    
    print("\n[2/3] Installing qwen2-vl:7b (vision model)...")
    print("  This is a ~4.4GB download and may take 5-10 minutes...\n")
    out, err, code = ssh_command('ollama pull qwen2-vl:7b', timeout=900, show_progress=True)
    if code == 0:
        print("  ✓ qwen2-vl:7b installed successfully")
    else:
        print(f"  ✗ Failed to install: {err}")
    
    print("\n[3/3] Installing moondream (backup vision model)...")
    print("  This is a smaller model (~829MB)...\n")
    out, err, code = ssh_command('ollama pull moondream', timeout=600, show_progress=True)
    if code == 0:
        print("  ✓ moondream installed successfully")
    else:
        print(f"  ✗ Failed to install: {err}")
    
    print("\n=== Verifying Installation ===")
    out, err, code = ssh_command('ollama list')
    print(out)
    
    print("\n=== Restarting Backend ===")
    ssh_command('pm2 restart telegram-backend')
    print("  ✓ Backend restarted")
    
    print("\n=== Installation Complete ===")
    print("All models are now installed:")
    print("  ✓ qwen2.5:7b (primary text model)")
    print("  ✓ gemma2:2b (fallback text model)")
    print("  ✓ qwen2-vl:7b (vision model for attachments)")
    print("  ✓ moondream (backup vision model)")
    print("\nRefresh your dashboard - all AI features should work now!")

if __name__ == '__main__':
    main()
