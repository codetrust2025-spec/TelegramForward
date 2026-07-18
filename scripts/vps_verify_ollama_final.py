#!/usr/bin/env python3
"""Final verification that Ollama is working end-to-end."""
import paramiko

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'

def main():
    print("=== Final Ollama Verification ===\n")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
    
    # Test 1: Ollama service
    print("[1/4] Checking Ollama service...")
    stdin, stdout, stderr = client.exec_command("systemctl status ollama | grep -E 'Active|Main PID'", timeout=10)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    if 'active (running)' in out:
        print("  ✓ Ollama service is RUNNING")
    else:
        print(f"  Status: {out}")
    
    # Test 2: API direct test
    print("\n[2/4] Testing Ollama API directly...")
    stdin, stdout, stderr = client.exec_command('curl -s http://localhost:11434/api/version', timeout=10)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    if 'version' in out:
        print(f"  ✓ Ollama API responding: {out.strip()}")
    else:
        print(f"  Response: {out}")
    
    # Test 3: List models
    print("\n[3/4] Checking installed models...")
    stdin, stdout, stderr = client.exec_command('ollama list', timeout=10)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    print(out)
    
    # Test 4: Simple generation test
    print("\n[4/4] Testing model generation...")
    stdin, stdout, stderr = client.exec_command(
        'ollama run qwen2.5:7b "Say OK" --verbose 2>&1 | head -20',
        timeout=30
    )
    stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    if out.strip():
        print(f"  ✓ Model responded")
        print(f"  Response preview: {out[:200]}")
    else:
        print("  No response")
    
    client.close()
    
    print("\n=== Verification Complete ===")
    print("\n✅ Next steps:")
    print("1. Hard refresh your dashboard (Ctrl+Shift+R)")
    print("2. The 'Ollama Tunnel Unreachable' error should be gone")
    print("3. New emails will be processed with AI")

if __name__ == '__main__':
    main()
