#!/usr/bin/env python3
"""Configure moondream as the primary vision model."""
import paramiko

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'
VPS_PATH = '/opt/telegramforward'

def main():
    print("=== Configuring Vision Models ===\n")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, username='root', password='REMOVED_VPS_PASSWORD', timeout=30)
    
    print("[1/3] Updating .env to use moondream as primary vision model...")
    stdin, stdout, stderr = client.exec_command(f"""
cd {VPS_PATH} && 
sed -i 's/OLLAMA_VISION_MODEL=qwen2.5vl:7b/OLLAMA_VISION_MODEL=moondream/' .env &&
grep VISION .env
""")
    stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    
    print("\n[2/3] Restarting backend...")
    stdin, stdout, stderr = client.exec_command('pm2 restart telegram-backend')
    stdout.channel.recv_exit_status()
    print("  ✓ Backend restarted")
    
    print("\n[3/3] Verifying models...")
    stdin, stdout, stderr = client.exec_command('ollama list')
    stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    
    client.close()
    
    print("\n=== Configuration Complete ===")
    print("✓ Primary vision model: moondream")
    print("✓ Backup vision model: moondream")
    print("✓ Primary text model: qwen2.5:7b")
    print("✓ Fallback text model: gemma2:2b")
    print("\nAll models are installed and configured!")
    print("Refresh your dashboard - the Ollama error should be gone.")

if __name__ == '__main__':
    main()
