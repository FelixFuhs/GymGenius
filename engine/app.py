from flask import Flask, request, jsonify
from predictions import extended_epley_1rm

app = Flask(__name__)

@app.route('/v1/predict/1rm/epley', methods=['POST'])
def predict_1rm_epley():
    data = request.get_json()
    if not data or 'weight' not in data or 'reps' not in data:
        return jsonify({"error": "Missing 'weight' or 'reps' in request body"}), 400

    try:
        weight = float(data['weight'])
        reps = int(data['reps'])
    except ValueError:
        return jsonify({"error": "Invalid 'weight' or 'reps' format. Must be numeric."}), 400

    if weight <= 0:
        return jsonify({"error": "'weight' must be positive."}), 400
    if reps < 1:
        # Or based on prediction model constraints, e.g. reps > 1 for Epley to make sense
        return jsonify({"error": "'reps' must be 1 or greater for Epley prediction."}), 400
        # extended_epley_1rm itself handles reps < 1 by returning 0,
        # but API can be stricter.

    estimated_1rm = extended_epley_1rm(weight, reps)

    return jsonify({
        "weight_input": weight,
        "reps_input": reps,
        "estimated_1rm_epley": estimated_1rm,
        "units": "same_as_input_weight" # Assuming weight unit is consistent
    })

if __name__ == '__main__':
    # This makes the app runnable for local development via `python app.py`
    # For docker, gunicorn or similar would be used.
    app.run(host='0.0.0.0', port=5000, debug=True)
