username="PUT_YOUR_USERNAME_HERE"
ombiver="v4.3.2"
systemctl stop ombi
cd /opt/
rm -rf Ombi
mkdir -p Ombi
wget -q https://github.com/Ombi-app/Ombi/releases/download/${ombiver}/linux-x64.tar.gz
tar -zxf linux-x64.tar.gz -C /opt/Ombi
rm -f linux-x64.tar.gz
sudo chown -R ${username}:${username} /opt/Ombi
chown -R ombi:nogroup /etc/Ombi
chown -R ombi:nogroup /opt/Ombi
systemctl start ombi