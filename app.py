# app.py
from flask import Flask, request, jsonify
import billing

app = Flask(__name__)

@app.route("/run", methods=["POST"])
def run_billing():
    # example: pass dummy argv or handle input
    try:
        billing.main(["input_arg"])
        return jsonify({"status": "completed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run()
