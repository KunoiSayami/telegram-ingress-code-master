## Use nginx reverse proxy

Put following text to configure file

```
location /path/set/in/config {
    proxy_pass http://127.0.0.1:29985;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_http_version 1.1;
    proxy_set_header      Upgrade "websocket";
    proxy_set_header      Connection "Upgrade";
    proxy_read_timeout    3600;
}
```

Then, reload nginx.