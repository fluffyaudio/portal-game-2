worker_class = "eventlet"
workers = 1
bind = "0.0.0.0:10000"
keepalive = 60
timeout = 120
worker_connections = 1000
wsgi_env = "EVENTLET_WEBSOCKET=1"
graceful_timeout = 60
worker_tmp_dir = "/dev/shm"
preload_app = False
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
reload = False
proxy_protocol = False
proxy_allow_ips = "*"
forwarded_allow_ips = "*"
