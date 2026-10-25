import time
import urllib.request

for attempt in range(45):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/api/ready", timeout=2)
        urllib.request.urlopen("http://127.0.0.1:5173", timeout=2)
        print("App is ready.")
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("App did not become ready in 45 seconds.")
