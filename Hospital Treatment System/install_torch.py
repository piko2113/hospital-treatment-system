import subprocess, sys, os

# 绕过可能的代理配置
env = os.environ.copy()
for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'REQUESTS_CA_BUNDLE']:
    env.pop(k, None)

# 用清华源 + 直接 wheel URL（CPU only，无 CUDA）
wheel_url = "https://download.pytorch.org/whl/cpu/torch-2.5.1%2Bcpu-cp39-cp39-win_amd64.whl"

print("下载 torch CPU 版（~205MB）...")
print("URL:", wheel_url)
result = subprocess.run([
    sys.executable, '-m', 'pip', 'install', '--no-deps', '--force-reinstall',
    wheel_url,
    '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple',
    '--trusted-host', 'download.pytorch.org',
    '--trusted-host', 'pypi.tuna.tsinghua.edu.cn',
], env=env, capture_output=True, text=True, timeout=600)

print("STDOUT:", result.stdout[-500:] if result.stdout else "")
print("STDERR:", result.stderr[-500:] if result.stderr else "")
print("Return code:", result.returncode)

if result.returncode == 0:
    print("\n✅ torch 安装成功！验证中...")
    import torch
    print(f"  版本: {torch.__version__}")
    print(f"  CUDA: {torch.cuda.is_available()}")
