import chromadb
try:
    client = chromadb.HttpClient(host="localhost", port=8000)
    print("Connection successful!")
    print(client.list_collections())
except Exception as e:
    print(f"Connection failed: {e}")
