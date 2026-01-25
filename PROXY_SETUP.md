# Self-Hosted Proxy Setup Guide (Seoul VPS)

This guide explains how to set up a cheap VPS in Seoul (e.g., Vultr, AWS Lightsail) as a proxy server for your Railway bot. This ensures the bot trades with a fixed Korean IP.

## 1. Get a VPS (Virtual Private Server)

Rent a small Linux server.
- **Provider**: [Vultr](https://www.vultr.com/) (Cloud Compute) or [AWS Lightsail](https://aws.amazon.com/lightsail/)
- **Region**: **Seoul (South Korea)** 🇰🇷
- **OS**: **Ubuntu 22.04** or 24.04
- **Size**: Smallest is fine ($5-6/month)

## 2. Connect to VPS

Use SSH to connect to your new server.
```bash
ssh root@<YOUR_VPS_IP>
# Enter password provided by the host
```

## 3. Run Setup Script

Run the following commands to install the proxy server automatically.
Replace `myuser` and `mypassword` with whatever you want to use for the proxy login.

```bash
# Download the script (copy-paste this line)
curl -o install_proxy.sh https://raw.githubusercontent.com/tns7gus-tech/cryptobot_studio/main/proxy_setup/install_proxy.sh

# Give permission
chmod +x install_proxy.sh

# Run installation
# Usage: ./install_proxy.sh <USERNAME> <PASSWORD>
./install_proxy.sh botuser securepass123
```

## 4. Get Your Proxy URL

After the installation finishes, the script will print your **PROXY_URL**:
```
http://botuser:securepass123@123.45.67.89:3128
```

## 5. Configure Railway

1. Go to **Railway Dashboard** -> **Variables**.
2. Create/Update variable: `PROXY_URL`
3. Paste the URL you got from step 4.
4. Redeploy.

## 6. Whitelist IP on Upbit

1. Copy your VPS IP address (`123.45.67.89`).
2. Go to **Upbit Open API Management**.
3. Add this IP to the allowlist.

Done! Your bot now runs on Railway but trades via Seoul.
