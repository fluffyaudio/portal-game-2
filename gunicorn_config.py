worker_class = "eventlet"
workers = 1
bind = "0.0.0.0:10000"
keepalive = 120
timeout = 300
worker_connections = 1000
wsgi_env = "EVENTLET_WEBSOCKET=1"
graceful_timeout = 300
worker_tmp_dir = "/dev/shm"  # Use shared memory for temp files
preload_app = True
