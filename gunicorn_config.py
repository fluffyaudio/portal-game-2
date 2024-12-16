worker_class = "eventlet"
workers = 1
bind = "0.0.0.0:10000"
keepalive = 120
timeout = 120
worker_connections = 1000
wsgi_env = "EVENTLET_WEBSOCKET=1"
