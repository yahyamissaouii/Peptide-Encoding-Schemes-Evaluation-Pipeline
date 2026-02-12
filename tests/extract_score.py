import requests
import pandas as pd
from io import BytesIO

BASE_URL = "https://tools.iedb.org"
FORM_URL = f"{BASE_URL}/pepsysco/"
CSV_URL = f"{FORM_URL}result_in_csv/"

sequence = "FSEFVFAATEFY"

session = requests.Session()

# 1) GET form page → obtain csrftoken + sessionid
r_get = session.get(FORM_URL)
r_get.raise_for_status()

csrf_token = session.cookies.get("csrftoken")
if not csrf_token:
    raise RuntimeError("CSRF token not found")

# 2) POST peptide sequence
data = {
    "csrfmiddlewaretoken": csrf_token,
    "sequence_text": sequence,
    "submit": "Submit",
}

files = {
    "sequence_file": ("", b"", "application/octet-stream")
}

headers = {
    "Origin": BASE_URL,
    "Referer": FORM_URL,
}

r_post = session.post(
    FORM_URL,
    data=data,
    files=files,
    headers=headers,
    allow_redirects=False,
)

if r_post.status_code != 302:
    raise RuntimeError(f"Submission failed: {r_post.status_code}")

# 3) GET CSV result (same session, new sessionid already stored)
r_csv = session.get(CSV_URL)
r_csv.raise_for_status()

if "text/csv" not in r_csv.headers.get("Content-Type", ""):
    raise RuntimeError("Did not receive CSV")

# 4) Load CSV into pandas
df = pd.read_csv(BytesIO(r_csv.content))

print(df)
