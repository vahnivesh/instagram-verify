from flask import Flask, request, render_template_string, redirect, url_for, jsonify, make_response
import secrets, time, requests, json
from flask_cors import CORS
import os




app = Flask(__name__)
CORS(app)

# =========================================
# SCRAPINGBOT API KEYS (PUT YOURS HERE)
# =========================================

SCRAPINGBOT_USERNAME = os.environ.get("SCRAPINGBOT_USERNAME")
SCRAPINGBOT_APIKEY = os.environ.get("SCRAPINGBOT_APIKEY")

SCRAPINGBOT_ENDPOINT = "http://api.scraping-bot.io/scrape/data-scraper"

# =========================================
# IN-MEMORY SESSION STORE
# =========================================

sessions = {}  
# {
#   uid: {
#       "username": str,
#       "code": str,
#       "expires_at": timestamp,
#       "verified": bool
#   }
# }


# =========================================
# BASE HTML TEMPLATE (TAILWIND)
# =========================================

BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>DIF – Instagram Bio Verification</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-white min-h-screen flex items-center justify-center px-4">

<div class="w-full max-w-lg bg-slate-800/50 backdrop-blur border border-slate-700 p-6 rounded-2xl shadow-xl">

    <div class="flex items-center gap-3 mb-6">
        <div class="w-10 h-10 rounded-xl bg-indigo-500 flex items-center justify-center font-bold">
            DIF
        </div>
        <div>
            <h1 class="text-xl font-semibold">Instagram Bio Verification</h1>
            <p class="text-xs text-slate-400">Prove identity by pasting a code.</p>
        </div>
    </div>

    {{ content|safe }}

</div>

<p class="mt-4 text-center text-xs text-slate-500">Onatt Tech – 2025</p>

</body>
</html>
"""

# =========================================
# UI PARTS
# =========================================

HOME_CONTENT = """
<form method="POST" class="space-y-5">
    <div>
        <label class="text-sm text-slate-300">Instagram username (without @)</label>
        <input name="username" required
               class="mt-1 w-full px-3 py-2 bg-slate-700 rounded-xl border border-slate-600"
               placeholder="vahnivesh">
    </div>

    <button class="w-full bg-indigo-500 hover:bg-indigo-600 rounded-xl py-2 font-semibold">
        Generate Code
    </button>
</form>
"""

DASHBOARD_CONTENT = """
<div class="space-y-5">

    <div class="p-4 bg-slate-700/40 rounded-xl border border-slate-600">
        <p class="text-xs text-slate-400">Instagram User</p>
        <p class="text-lg font-semibold">@{{ username }}</p>
    </div>

    {% if verified %}
        <div class="p-4 bg-emerald-500/10 border border-emerald-500/40 rounded-xl">
            <p class="text-xl text-emerald-300 font-bold">✔ Verified!</p>
            <p class="text-sm text-emerald-200">Your code was found in your Instagram bio.</p>
        </div>
    {% else %}

        <div class="p-4 bg-slate-700/40 rounded-xl border border-slate-600">
            <p class="text-xs text-slate-400">Your Verification Code</p>
            <p class="text-2xl font-mono text-indigo-400 font-bold">{{ code }}</p>

            {% if expired %}
                <p class="text-sm text-red-300 mt-2">Code expired. Generate a new one.</p>
            {% else %}
                <p class="text-xs text-slate-400 mt-2">Valid for 10 minutes.</p>
            {% endif %}
        </div>

        <div class="p-4 bg-slate-700/40 rounded-xl border border-slate-600">
            <p class="text-sm font-medium mb-2">How to verify</p>
            <ol class="text-xs text-slate-400 space-y-1">
                <li>1. Edit your Instagram bio.</li>
                <li>2. Paste this code: <b class="text-indigo-300">{{ code }}</b></li>
                <li>3. Save your profile.</li>
                <li>4. Click “Check Bio”.</li>
            </ol>
        </div>

        {% if not expired %}
        <a href="/checking/{{uid}}" 
           class="w-full block text-center mt-2 bg-indigo-500 hover:bg-indigo-600 py-2 rounded-xl">
            Check Bio
        </a>
        {% endif %}

    {% endif %}

    <div class="flex gap-3 mt-4">
        <a href="/" class="flex-1 text-center py-2 rounded-xl bg-slate-700 border border-slate-600">
            Start Over
        </a>
        <a href="{{ url_for('dashboard', uid=uid) }}" 
           class="flex-1 text-center py-2 rounded-xl bg-indigo-500">
            Refresh
        </a>
    </div>

</div>
"""


# =========================================
# LOADING SCREEN (ANIMATED DOTS)
# =========================================

CHECKING_HTML = """
<div class="text-center space-y-4">
    <h2 class="text-xl font-semibold text-indigo-400">Verifying your bio…</h2>
    <p id="dots" class="text-slate-300 text-sm">Please wait</p>
</div>

<script>
    let dots = document.getElementById("dots");
    let count = 0;
    setInterval(() => {
        count = (count + 1) % 4;
        dots.innerText = "Please wait" + ".".repeat(count);
    }, 500);

    setTimeout(() => {
        window.location.href = "/check_bio?uid={{uid}}";
    }, 12000);
</script>
"""


# =========================================
# SCRAPINGBOT FUNCTION (FINAL FIXED)
# =========================================

def scrape_instagram_bio(username):
    """
    FINAL version — fully compatible with ScrapingBot's actual behavior.
    Handles:
    - list responses with final data
    - dict 'pending' message
    - anti-flood errors
    - no-status final responses
    """

    payload = json.dumps({
        "scraper": "instagramProfile",
        "account": username,
        "posts_number": "1"
    })

    headers = {"Content-Type": "application/json"}

    # STEP 1 — Start scrape job
    r = requests.post(
        SCRAPINGBOT_ENDPOINT,
        data=payload,
        headers=headers,
        auth=(SCRAPINGBOT_USERNAME, SCRAPINGBOT_APIKEY)
    )

    start_data = r.json()
    print("\nSTART:", start_data)

    # Normalize list
    if isinstance(start_data, list):
        start_data = start_data[0]

    response_id = start_data.get("responseId")
    if not response_id:
        print("❌ ERROR: No responseId")
        return None

    # STEP 2 — Poll for result
    while True:
        time.sleep(3)

        poll_url = (
            f"http://api.scraping-bot.io/scrape/data-scraper-response?"
            f"scraper=instagramProfile&responseId={response_id}"
        )

        rr = requests.get(poll_url, auth=(SCRAPINGBOT_USERNAME, SCRAPINGBOT_APIKEY))
        raw = rr.json()

        print("POLL:", raw)

        # A) If anti flood
        if isinstance(raw, dict) and raw.get("error"):
            print("WAITING (anti-flood)...")
            time.sleep(2)
            continue

        # B) If final response is a LIST → this IS finished
        if isinstance(raw, list) and len(raw) > 0:
            final_obj = raw[0]
            bio = final_obj.get("biography")
            print("BIO FOUND (LIST):", bio)
            return bio

        # C) If pending
        if raw.get("status") == "pending":
            continue

        # D) If direct profile dict response (rare case)
        if "biography" in raw:
            print("BIO FOUND (DIRECT):", raw["biography"])
            return raw["biography"]

        # Unknown
        print("❓ UNKNOWN RESPONSE:", raw)
        return None


# =========================================
# ROUTES
# =========================================


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "GET":
        return render_template_string(BASE_HTML, content=HOME_CONTENT)

    username = request.form["username"].strip().lower().lstrip("@")

    uid = secrets.token_hex(6)
    code = "DIF-" + secrets.token_hex(3).upper()
    expires_at = time.time() + 10 * 60

    sessions[uid] = {
        "username": username,
        "code": code,
        "expires_at": expires_at,
        "verified": False
    }

    return redirect(url_for("dashboard", uid=uid))


@app.route("/dashboard/<uid>")
def dashboard(uid):
    s = sessions.get(uid)
    if not s:
        return "Invalid session", 404

    expired = (time.time() > s["expires_at"])

    return render_template_string(
        BASE_HTML,
        content=render_template_string(
            DASHBOARD_CONTENT,
            username=s["username"],
            code=s["code"],
            verified=s["verified"],
            expired=expired,
            uid=uid
        )
    )


@app.route("/checking/<uid>")
def checking(uid):
    if uid not in sessions:
        return "Invalid session", 404

    return render_template_string(BASE_HTML,
                                  content=CHECKING_HTML.replace("{{uid}}", uid))


@app.route("/check_bio")
def check_bio():
    uid = request.args.get("uid")
    s = sessions.get(uid)

    if not s:
        return "Invalid session", 404

    if time.time() > s["expires_at"]:
        return redirect(url_for("dashboard", uid=uid))

    username = s["username"]
    code = s["code"]

    bio = scrape_instagram_bio(username)
    print("BIO EXTRACTED:", bio)

    if bio and code in bio:
        s["verified"] = True

    return redirect(url_for("dashboard", uid=uid))


# =========================================
# RUN APP
# =========================================

@app.route("/api/check_instagram", methods=["POST", "OPTIONS"])
def api_check_instagram():
    """
    JSON API used by the DIF frontend.
    Request JSON: { "username": "...", "code": "..." }
    Response JSON: { "verified": bool, "bio_found": bool }
    """

    # Handle CORS preflight
    if request.method == "OPTIONS":
        resp = make_response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower().lstrip("@")
    code = (data.get("code") or "").strip()

    if not username or not code:
        resp = jsonify({"verified": False, "bio_found": False, "error": "missing_fields"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 400

    bio = scrape_instagram_bio(username)
    ok = bool(bio and code in bio)

    resp = jsonify({
        "verified": ok,
        "bio_found": bool(bio),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



