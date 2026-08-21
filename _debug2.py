import json

# IP
d = json.load(open('_d_ip.json','r',encoding='utf-8'))
inner = d['data']['data']
for source, data in inner.items():
    print(f"IP Source: {source}")
    if isinstance(data, dict):
        print(f"  Keys: {list(data.keys())[:10]}")

# Vehicle
d2 = json.load(open('_d_vh.json','r',encoding='utf-8'))
resp = d2['data']['response']
print(f"Vehicle keys: {list(resp.keys())[:15]}")

# HotX
d3 = json.load(open('_d_hx.json','r',encoding='utf-8'))
hx = d3['data']['result']['response']['data']
t = type(hx).__name__
print(f"HotX type: {t}")
if isinstance(hx, list) and hx:
    print(f"HotX[0] keys: {list(hx[0].keys())[:15]}")
elif isinstance(hx, dict):
    print(f"HotX keys: {list(hx.keys())[:15]}")
