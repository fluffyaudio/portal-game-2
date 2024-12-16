worker_class = "eventlet"
workers = 1
bind = "0.0.0.0:10000"
keepalive = 300
timeout = 600
worker_connections = 1000
wsgi_env = "EVENTLET_WEBSOCKET=1"
graceful_timeout = 300
worker_tmp_dir = "/tmp"  # Use standard temp directory instead of /dev/shm
preload_app = False  # Disable preloading to avoid file descriptor issues
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log errors to stdout
loglevel = "info"
capture_output = True
reload = True
proxy_protocol = True
proxy_allow_ips = "*"
forwarded_allow_ips = "*"
