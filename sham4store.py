import os,uuid,requests
class Sham4StoreAPI:
 def __init__(self):
  self.base_url=os.getenv("SHAM4STORE_BASE_URL","https://api.sham4store.com").rstrip("/")
  self.headers={"api-token":os.getenv("SHAM_STORE_API_TOKEN",""),"Accept":"application/json"}
 def get_products(self):
  r=requests.get(self.base_url+"/client/api/products",params={"base":1},headers=self.headers,timeout=25);r.raise_for_status();return r.json()
 def create_order(self,product_id,player_id,quantity=1):
  return requests.get(self.base_url+f"/client/api/newOrder/{int(product_id)}/params",params={"qty":quantity,"playerId":player_id,"order_uuid":str(uuid.uuid4())},headers=self.headers,timeout=30).json()
