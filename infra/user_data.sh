#!/usr/bin/env bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

apt-get update
apt-get install -y docker.io nginx git sqlite3 curl fail2ban
snap install aws-cli --classic

useradd -m -s /bin/bash dockship
usermod -aG docker dockship
mkdir -p /opt/dockship /var/lib/dockship /etc/nginx/conf.d/dockship
chown dockship:dockship /opt/dockship /var/lib/dockship /etc/nginx/conf.d/dockship

rm -f /etc/nginx/sites-enabled/default
install -m 0644 /dev/null /etc/nginx/conf.d/00-dockship.conf
cat > /etc/nginx/conf.d/00-dockship.conf <<'EOF'
include /etc/nginx/conf.d/dockship/*.conf;
server {
    listen 80 default_server;
    server_name _;
    return 444;
}
EOF

cat > /etc/sudoers.d/dockship <<'EOF'
dockship ALL=(root) NOPASSWD: /usr/sbin/nginx -t, /usr/bin/systemctl reload nginx, /usr/bin/systemctl restart dockship
EOF
visudo -cf /etc/sudoers.d/dockship

sudo -u dockship -H bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
systemctl enable --now docker nginx fail2ban
