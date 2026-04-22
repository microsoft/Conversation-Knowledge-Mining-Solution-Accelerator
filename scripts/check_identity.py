from azure.identity import DefaultAzureCredential
import json, base64

cred = DefaultAzureCredential()
tok = cred.get_token("https://storage.azure.com/.default")
parts = tok.token.split(".")
payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
claims = json.loads(base64.b64decode(payload))
print(f"Identity: {claims.get('upn', claims.get('appid', '?'))}")
print(f"oid: {claims.get('oid')}")
print(f"tenant: {claims.get('tid')}")
