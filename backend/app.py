import requests
import subprocess
import os
import json
import crypt
from datetime import datetime
from flask_httpauth import HTTPBasicAuth
from flask import Flask, jsonify, request
from registry_api import check_registry_alive, get_image_repositories, get_image_tags

HTPASSWD_PATH = "/auth/htpasswd"
REGISTRY_URL = "http://private_registry:5000"
AUDIT_LOG_PATH = "/app/audit.log"

app = Flask(__name__)
auth = HTTPBasicAuth()

def load_users():
    users = {}
    with open(HTPASSWD_PATH) as f:
        for line in f:
            user, hashed = line.strip().split(":")
            users[user] = hashed
    return users

@auth.verify_password
def verify(username, password):
    users = load_users()
    hashed = users.get(username)
    if hashed:
        return crypt.crypt(password, hashed) == hashed
    return False

@app.route('/ping')
@auth.login_required
def ping():
    return {"status": "ok"}

@app.route('/registry/ping')
@auth.login_required
def registry_ping():
    status, body = check_registry_alive()
    return {"status_code": status, "body": body}

@app.route('/images')
@auth.login_required
def list_images():
    images = get_image_repositories()
    return {"images": images}

@app.route('/images/<image_name>/tags')
@auth.login_required
def image_tags(image_name):
    tags = get_image_tags(image_name)
    return {"tags": tags}

@app.route('/images/<name>/tags/<tag>', methods=['DELETE'])
@auth.login_required
def delete_image_tag(name, tag):
    # 요청자 인증 정보 사용
    auth_info = request.authorization

    # 1단계: 해당 이미지의 manifest digest 가져오기
    manifest_url = f"{REGISTRY_URL}/v2/{name}/manifests/{tag}"
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    
    resp = requests.get(manifest_url, headers=headers, auth=(auth_info.username, auth_info.password))

    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch manifest", "status_code": resp.status_code}), resp.status_code

    digest = resp.headers.get("Docker-Content-Digest")
    if not digest:
        return jsonify({"error": "Digest not found in headers"}), 500

    # 2단계: manifest 삭제 요청 (하드코딩 제거)
    delete_url = f"{REGISTRY_URL}/v2/{name}/manifests/{digest}"
    del_resp = requests.delete(delete_url, auth=(auth_info.username, auth_info.password))

    if del_resp.status_code == 202:
        return jsonify({"message": f"{name}:{tag} deleted successfully"}), 200
    else:
        return jsonify({"error": "Failed to delete", "status_code": del_resp.status_code}), del_resp.status_code
    
@app.route('/images/<name>', methods=['DELETE'])
@auth.login_required
def delete_entire_image(name):
    auth_info = request.authorization

    # 1. 태그 목록 조회
    tags_url = f"{REGISTRY_URL}/v2/{name}/tags/list"
    tags_resp = requests.get(tags_url, auth=(auth_info.username, auth_info.password))
    
    if tags_resp.status_code != 200:
        return jsonify({"error": "Failed to fetch tag list", "status_code": tags_resp.status_code}), tags_resp.status_code

    tags = tags_resp.json().get("tags")
    if not tags:
        return jsonify({"message": f"No tags found for image '{name}'"}), 200

    deleted_tags = []
    failed_tags = []

    # 2. 태그마다 digest 조회 후 삭제
    for tag in tags:
        manifest_url = f"{REGISTRY_URL}/v2/{name}/manifests/{tag}"
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        manifest_resp = requests.get(manifest_url, headers=headers, auth=(auth_info.username, auth_info.password))

        if manifest_resp.status_code != 200:
            failed_tags.append({"tag": tag, "reason": f"manifest fetch failed ({manifest_resp.status_code})"})
            continue

        digest = manifest_resp.headers.get("Docker-Content-Digest")
        if not digest:
            failed_tags.append({"tag": tag, "reason": "digest not found"})
            continue

        delete_url = f"{REGISTRY_URL}/v2/{name}/manifests/{digest}"
        delete_resp = requests.delete(delete_url, auth=(auth_info.username, auth_info.password))

        if delete_resp.status_code == 202:
            deleted_tags.append(tag)
        else:
            failed_tags.append({"tag": tag, "reason": f"delete failed ({delete_resp.status_code})"})

    return jsonify({
        "image": name,
        "deleted_tags": deleted_tags,
        "failed_tags": failed_tags
    }), 200

@app.route('/users', methods=['POST'])
@auth.login_required
def add_user():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    try:
        import os
        if not os.path.exists(HTPASSWD_PATH):
            cmd = ["htpasswd", "-Bbc", HTPASSWD_PATH, username, password]
        else:
            cmd = ["htpasswd", "-Bb", HTPASSWD_PATH, username, password]

        result = subprocess.run(cmd, capture_output=True, check=True, text=True)

        global USERS
        USERS = load_users()

        return jsonify({"message": f"User '{username}' added"}), 201
    except subprocess.CalledProcessError as e:
        return jsonify({
            "error": "Failed to create user",
            "cmd": cmd,
            "stderr": e.stderr
        }), 500

@app.route('/users/<username>', methods=['DELETE'])
@auth.login_required
def delete_user(username):
    htpasswd_path = "/auth/htpasswd"
    
    # 먼저 htpasswd 파일이 존재하는지 확인
    if not os.path.exists(htpasswd_path):
        return jsonify({"error": "htpasswd file not found"}), 500

    # 사용자 존재 여부 확인
    with open(htpasswd_path, 'r') as f:
        lines = f.readlines()
        if not any(line.startswith(username + ":") for line in lines):
            return jsonify({"message": f"User '{username}' not found"}), 404

    # 삭제 시도
    cmd = ["htpasswd", "-D", htpasswd_path, username]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if result.returncode == 0:
        global USERS
        USERS = load_users()

        return jsonify({"message": f"User '{username}' deleted"}), 200
    else:
        return jsonify({
            "error": "Failed to delete user",
            "stderr": result.stderr.decode()
        }), 500

@app.after_request
def log_request(response):
    log_data = {
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "timestamp": datetime.utcnow().isoformat()
    }

    auth_info = request.authorization
    if auth_info and auth_info.username:
        log_data["user"] = auth_info.username

    try:
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(log_data) + "\n")
    except Exception as e:
        print("Failed to write audit log:", e)

    return response

@app.route("/audit", methods=["GET"])
@auth.login_required
def get_audit_logs():
    user_filter = request.args.get("user")
    image_filter = request.args.get("image")

    try:
        with open(AUDIT_LOG_PATH, "r") as f:
            lines = f.readlines()
            logs = [json.loads(line.strip()) for line in lines]

        # 필터링 조건 적용
        if user_filter:
            logs = [log for log in logs if log.get("user") == user_filter]
        if image_filter:
            logs = [log for log in logs if f"/images/{image_filter}" in log["path"]]

        return jsonify(logs)

    except FileNotFoundError:
        return jsonify([])  # 로그 파일 없으면 빈 배열
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/init', methods=['POST'])
def initialize_admin():
    if os.path.exists(HTPASSWD_PATH):
        with open(HTPASSWD_PATH) as f:
            for line in f:
                if line.startswith("admin:"):
                    return "Admin already exists", 403

    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    cmd = ["htpasswd", "-Bbc", HTPASSWD_PATH, username, password]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return jsonify({"message": f"Admin '{username}' initialized"}), 201
    else:
        return jsonify({
            "error": "Failed to initialize admin",
            "stderr": result.stderr
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)