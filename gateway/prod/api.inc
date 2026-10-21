# Shared by every site: API routing, chat WebSocket, public media. (Map defined in nginx.conf.)
location /api/internal/ { return 404; }

location /api/chat/ws/ {
    set $chat_upstream chat;
    proxy_pass http://$chat_upstream:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 1h;
}

location /api/ {
    if ($service = "") { return 404; }
    proxy_pass http://$service:8000;
}

location /media/public/ {
    alias /data/media/public/;
    expires 7d;
}

location = /health { return 200 "ok\n"; }
