RWRiter Data Flow:

+----------------+        +-----------+        +------------------+
|  Frontend UI   |  <---> |  proxy.php|  <---> | FastAPI Backend  |
|  (index.php)   |        | (PHP)     |        | (main.py)        |
+----------------+        +-----------+        +------------------+
        |                                              |
        |                                              |
        v                                              v
  User actions                                    Chat history &
  (send/receive)                                  context stored in:
                                                   /rwriter/userdata/
                                                   /{username}/{chatname}/data.json
