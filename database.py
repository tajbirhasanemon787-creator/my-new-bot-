import json
import os

class Database:
    def __init__(self):
        self.db_file = "/tmp/bot_database.json" if os.getenv("VERCEL") else "bot_database.json"
        if not os.path.exists(self.db_file):
            self.data = {"users": {}, "tasks": [], "withdrawals": []}
            self.save()
        else:
            self.load()

    def load(self):
        try:
            with open(self.db_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except:
            self.data = {"users": {}, "tasks": [], "withdrawals": []}

    def save(self):
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def register_user(self, user_id, name, username, ref_id=None):
        self.load()
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "user_id": user_id,
                "name": name,
                "username": username,
                "balance": 0.0,
                "total_earned": 0.0,
                "tasks_done": 0,
                "referrals": 0,
                "total_withdrawn": 0.0,
                "completed_tasks": []
            }
            if ref_id and str(ref_id) in self.data["users"]:
                self.data["users"][str(ref_id)]["referrals"] += 1
            self.save()
            return True
        return False

    def get_balance(self, user_id):
        self.load()
        return self.data["users"].get(str(user_id), {}).get("balance", 0.0)

    def add_balance(self, user_id, amount):
        self.load()
        uid = str(user_id)
        if uid in self.data["users"]:
            self.data["users"][uid]["balance"] += amount
            self.data["users"][uid]["total_earned"] += amount
            self.save()

    def deduct_balance(self, user_id, amount):
        self.load()
        uid = str(user_id)
        if uid in self.data["users"] and self.data["users"][uid]["balance"] >= amount:
            self.data["users"][uid]["balance"] -= amount
            self.save()

    def get_user_stats(self, user_id):
        self.load()
        u = self.data["users"].get(str(user_id), {})
        return {
            "tasks_done": u.get("tasks_done", 0),
            "referrals": u.get("referrals", 0),
            "total_withdrawn": u.get("total_withdrawn", 0.0)
        }

    def get_active_tasks(self):
        self.load()
        return self.data["tasks"]

    def get_task(self, task_id):
        self.load()
        for t in self.data["tasks"]:
            if t["id"] == task_id:
                return t
        return None

    def is_task_completed(self, user_id, task_id):
        self.load()
        u = self.data["users"].get(str(user_id), {})
        return task_id in u.get("completed_tasks", [])

    def get_completed_count(self, user_id):
        self.load()
        u = self.data["users"].get(str(user_id), {})
        return len(u.get("completed_tasks", []))

    def complete_task(self, user_id, task_id):
        self.load()
        uid = str(user_id)
        if uid in self.data["users"]:
            if task_id not in self.data["users"][uid]["completed_tasks"]:
                self.data["users"][uid]["completed_tasks"].append(task_id)
                self.data["users"][uid]["tasks_done"] += 1
                self.save()

    def get_leaderboard(self):
        self.load()
        users_list = list(self.data["users"].values())
        users_list.sort(key=lambda x: x.get("total_earned", 0.0), reverse=True)
        return users_list[:10]

    def create_withdrawal(self, user_id, amount, method, phone):
        self.load()
        req_id = len(self.data["withdrawals"]) + 1
        name = self.data["users"].get(str(user_id), {}).get("name", "Unknown")
        req = {
            "id": req_id, "user_id": user_id, "name": name, "amount": amount,
            "method": method, "phone": phone, "status": "pending"
        }
        self.data["withdrawals"].append(req)
        self.save()
        return req_id

    def get_pending_withdrawals(self):
        self.load()
        return [w for w in self.data["withdrawals"] if w["status"] == "pending"]

    def get_withdrawal(self, req_id):
        self.load()
        for w in self.data["withdrawals"]:
            if w["id"] == req_id:
                return w
        return None

    def update_withdrawal(self, req_id, status):
        self.load()
        for w in self.data["withdrawals"]:
            if w["id"] == req_id:
                w["status"] = status
                if status == "approved":
                    uid = str(w["user_id"])
                    if uid in self.data["users"]:
                        self.data["users"][uid]["total_withdrawn"] += w["amount"]
                self.save()
                break

    def get_bot_stats(self):
        self.load()
        return {
            "total_users": len(self.data["users"]),
            "tasks_completed": sum(u.get("tasks_done", 0) for u in self.data["users"].values()),
            "total_withdrawn": sum(w["amount"] for w in self.data["withdrawals"] if w["status"] == "approved"),
            "pending_withdrawals": len([w for w in self.data["withdrawals"] if w["status"] == "pending"]),
            "active_tasks": len(self.data["tasks"])
        }

    def add_task(self, title, description, link, reward):
        self.load()
        tid = len(self.data["tasks"]) + 1
        task = {"id": tid, "title": title, "description": description, "link": link, "reward": reward}
        self.data["tasks"].append(task)
        self.save()
        return tid

    def delete_task(self, task_id):
        self.load()
        self.data["tasks"] = [t for t in self.data["tasks"] if t["id"] != task_id]
        self.save()

    def get_all_users(self):
        self.load()
        return list(self.data["users"].values())
