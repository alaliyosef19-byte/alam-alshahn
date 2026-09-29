from flask import Flask, render_template, request, jsonify
from sham4store import Sham4StoreAPI
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret")

api = Sham4StoreAPI()

@app.route('/')
def home():
    products_data = api.get_products()
    return render_template('index.html', products=products_data)

@app.route('/api/balance', methods=['GET'])
def check_balance():
    balance_info = api.get_balance()
    return jsonify(balance_info)

@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.get_json()
    product_id = data.get('product_id')
    player_id = data.get('player_id')
    quantity = data.get('quantity', 1)

    if not product_id or not player_id:
        return jsonify({"success": False, "message": "جميع الحقول مطلوبة"}), 400

    result = api.create_order(product_id=product_id, player_id=player_id, quantity=quantity)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
