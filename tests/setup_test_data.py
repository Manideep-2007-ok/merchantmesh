import urllib.request

path = "data/test_images/saree.jpg"
url = "https://images.unsplash.com/photo-1610030469983-98e550d615ef?w=500&q=80"
print("Downloading saree...")
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
        out_file.write(response.read())
except Exception as e:
    print(f"Error: {e}")
