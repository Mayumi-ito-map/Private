# GoogleAPIを試す

import json
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise SystemExit("GOOGLE_API_KEY が .env にありません")

address = "서울" # 調べる地名
params = urllib.parse.urlencode({"address": address, "key": api_key})
url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"

with urllib.request.urlopen(url) as resp:
    data = json.load(resp)

print("status:", data.get("status"))
print(json.dumps(data, ensure_ascii=False, indent=2))