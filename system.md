[Unit]
Description=Photo Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/photoserver/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
