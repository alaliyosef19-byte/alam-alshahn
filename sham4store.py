import os
import uuid
import requests
from dotenv import load_dotenv

load_dotenv()


class Sham4StoreAPI:
    def __init__(self):
        self.base_url = os.getenv(
            "SHAM4STORE_BASE_URL",
            "https://api.sham4store.com"
        ).rstrip("/")

        self.api_token = os.getenv("SHAM4STORE_API_KEY")

        self.headers = {
            "api-token": self.api_token,
            "Accept": "application/json"
        }

    def get_balance(self):
        try:
            response = requests.get(
                f"{self.base_url}/client/api/profile",
                headers=self.headers,
                timeout=10
            )
            return response.json()

        except requests.RequestException as e:
            return {
                "status": False,
                "message": f"خطأ في الاتصال: {e}"
            }

    def get_products(self):
        try:
            response = requests.get(
                f"{self.base_url}/client/api/products",
                headers=self.headers,
                timeout=10
            )
            return response.json()

        except requests.RequestException as e:
            return {
                "status": False,
                "message": f"تعذر جلب المنتجات: {e}"
            }

    def create_order(self, product_id, player_id, quantity=1):
        order_uuid = str(uuid.uuid4())

        params = {
            "qty": quantity,
            "playerId": player_id,
            "order_uuid": order_uuid
        }

        try:
            response = requests.get(
                f"{self.base_url}/client/api/newOrder/{product_id}/params",
                params=params,
                headers=self.headers,
                timeout=15
            )

            return response.json()

        except requests.RequestException as e:
            return {
                "status": False,
                "message": f"فشل تنفيذ الطلب: {e}"
            }
