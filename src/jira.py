import base64
import time

import requests


class JiraClient:
    def __init__(self, domain, email, token, project_key):
        self.base = f"https://{domain.rstrip('/')}"
        self.project_key = project_key
        auth = base64.b64encode(f"{email}:{token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path, **params):
        r = requests.get(f"{self.base}{path}", headers=self.headers, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def _post(self, path, body):
        r = requests.post(f"{self.base}{path}", headers=self.headers, json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    def _post_retry(self, path, body, retries=3):
        for attempt in range(retries):
            try:
                return self._post(path, body)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return self._post(path, body)

    def test_connection(self):
        try:
            data = self._get(f"/rest/api/3/project/{self.project_key}")
            return {"ok": True, "message": f"Connected — {data.get('name')}", "project": data}
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            return {"ok": False, "message": f"HTTP {code}: {e}", "project": None}
        except Exception as e:
            return {"ok": False, "message": str(e), "project": None}

    def get_board_id(self):
        try:
            data = self._get("/rest/agile/1.0/board", projectKeyOrId=self.project_key, type="scrum")
            values = data.get("values", [])
            return values[0]["id"] if values else None
        except Exception:
            return None

    def create_epic(self, name, summary):
        body = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "issuetype": {"name": "Epic"},
                "customfield_10011": name,
            }
        }
        try:
            return self._post_retry("/rest/api/3/issue", body)
        except requests.HTTPError:
            # classic projects don't always have customfield_10011
            body["fields"].pop("customfield_10011", None)
            return self._post_retry("/rest/api/3/issue", body)

    def create_issue(self, title, description, issue_type, priority, story_points, epic_key, acceptance_criteria):
        desc_text = description + "\n\nAcceptance Criteria:\n" + "\n".join(f"- {c}" for c in acceptance_criteria)
        body = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": title,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": desc_text}]}],
                },
                "issuetype": {"name": issue_type if issue_type in ("Story", "Task", "Bug") else "Story"},
                "priority": {"name": priority},
                "customfield_10016": story_points,
            }
        }
        if epic_key:
            body["fields"]["parent"] = {"key": epic_key}
        return self._post_retry("/rest/api/3/issue", body)

    def create_sprint(self, board_id, name, goal):
        return self._post_retry("/rest/agile/1.0/sprint", {"name": name, "goal": goal, "originBoardId": board_id})

    def add_to_sprint(self, sprint_id, issue_keys):
        self._post_retry(f"/rest/agile/1.0/sprint/{sprint_id}/issue", {"issues": issue_keys})

    def sync_plan(self, plan):
        """Generator — yields progress dicts so the UI can show live updates."""
        tasks = plan.get("tasks", [])
        sprints_meta = plan.get("sprints", [])

        # 1. Create one Epic per module
        modules = list({t["module"] for t in tasks if t.get("module")})
        epic_map = {}
        for i, module in enumerate(modules, 1):
            try:
                result = self.create_epic(module, f"[Epic] {module}")
                key = result["key"]
                epic_map[module] = key
                yield {"phase": "Epics", "done": i, "total": len(modules), "key": key, "url": f"{self.base}/browse/{key}", "error": None}
            except Exception as e:
                yield {"phase": "Epics", "done": i, "total": len(modules), "key": "", "url": "", "error": str(e)}

        # 2. Create Issues
        issue_map = {}
        for i, task in enumerate(tasks, 1):
            try:
                result = self.create_issue(
                    title=task["title"],
                    description=task.get("description", ""),
                    issue_type=task.get("type", "Story"),
                    priority=task.get("priority", "Medium"),
                    story_points=task.get("story_points", 3),
                    epic_key=epic_map.get(task.get("module", "")),
                    acceptance_criteria=task.get("acceptance_criteria", []),
                )
                key = result["key"]
                issue_map[task["id"]] = key
                yield {"phase": "Issues", "done": i, "total": len(tasks), "key": key, "url": f"{self.base}/browse/{key}", "error": None}
            except Exception as e:
                yield {"phase": "Issues", "done": i, "total": len(tasks), "key": "", "url": "", "error": str(e)}

        # 3. Create Sprints and assign issues
        board_id = self.get_board_id()
        for i, sm in enumerate(sprints_meta, 1):
            name = sm["name"]
            try:
                if board_id:
                    sprint = self.create_sprint(board_id, name, sm.get("goal", ""))
                    sid = sprint["id"]
                    keys = [issue_map[tid] for tid in sm.get("task_ids", []) if tid in issue_map]
                    if keys:
                        self.add_to_sprint(sid, keys)
                    yield {"phase": "Sprints", "done": i, "total": len(sprints_meta), "key": name, "url": "", "error": None}
                else:
                    yield {"phase": "Sprints", "done": i, "total": len(sprints_meta), "key": name, "url": "", "error": "No scrum board found — sprint skipped"}
            except Exception as e:
                yield {"phase": "Sprints", "done": i, "total": len(sprints_meta), "key": name, "url": "", "error": str(e)}

        yield {"phase": "done", "epic_map": epic_map, "issue_map": issue_map}
