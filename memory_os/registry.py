from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from scripts.memory_common import load_json, sanitize_project_name, utc_now, write_json_atomic

from .fingerprint import git_score, jaccard_dict, manifest_score
from .schemas import ProjectDetectionResult
from .vector_store import VectorStore


def project_id_for(root: Path, fingerprint: dict[str, Any]) -> str:
    seed = fingerprint.get("git_remote") or fingerprint.get("git_top") or str(root.resolve())
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"{sanitize_project_name(root.name)}-{digest}"


class ProjectRegistry:
    def __init__(self, memory_root: Path, vector_store: VectorStore, threshold: float) -> None:
        self.memory_root = memory_root
        self.vector_store = vector_store
        self.threshold = threshold
        self.path = memory_root / "project_registry.json"
        self.memory_root.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        data = load_json(self.path, {"version": 1, "projects": {}, "feedback": []})
        data.setdefault("projects", {})
        data.setdefault("feedback", [])
        return data

    def save(self, data: dict[str, Any]) -> None:
        write_json_atomic(self.path, data)

    def score_candidate(self, fingerprint: dict[str, Any], candidate: dict[str, Any], embedding_score: float) -> tuple[float, dict[str, float]]:
        candidate_fp = candidate.get("fingerprint", {})
        structure = jaccard_dict(fingerprint.get("top_dirs", {}), candidate_fp.get("top_dirs", {})) * 0.25
        dependency = manifest_score(fingerprint.get("manifests", []), candidate_fp.get("manifests", [])) * 0.20
        embedding = embedding_score * 0.35
        git = git_score(fingerprint, candidate_fp) * 0.20
        score = structure + dependency + embedding + git
        return score, {
            "structure_score": round(structure, 4),
            "dependency_score": round(dependency, 4),
            "embedding_similarity": round(embedding, 4),
            "git_signal": round(git, 4),
            "total": round(score, 4),
        }

    def detect(self, root: Path, fingerprint: dict[str, Any]) -> ProjectDetectionResult:
        registry = self.load()
        projects = registry["projects"]
        collection = self.vector_store.registry()
        embedding_candidates: dict[str, float] = {}
        count = collection.count()
        if count:
            results = collection.query(query_texts=[fingerprint["identity_text"]], n_results=min(10, count))
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0] or [1.0] * len(ids)
            for project_id, distance in zip(ids, distances):
                embedding_candidates[project_id] = max(0.0, 1.0 - float(distance))

        best_id: str | None = None
        best_score = -1.0
        best_scores: dict[str, float] = {}
        for project_id, project in projects.items():
            score, scores = self.score_candidate(fingerprint, project, embedding_candidates.get(project_id, 0.0))
            if score > best_score:
                best_id = project_id
                best_score = score
                best_scores = scores

        if best_id and best_score > self.threshold:
            project = projects[best_id]
            project["last_seen"] = utc_now()
            project["roots"] = sorted(set([*project.get("roots", []), str(root.resolve())]))
            project["fingerprint"] = fingerprint
            self.save(registry)
            return ProjectDetectionResult(
                project_id=best_id,
                project_name=project["name"],
                confidence=round(best_score, 4),
                is_new=False,
                scores=best_scores,
                root=str(root.resolve()),
            )

        new_id = project_id_for(root, fingerprint)
        projects[new_id] = {
            "project_id": new_id,
            "name": fingerprint["name"],
            "roots": [str(root.resolve())],
            "created_at": utc_now(),
            "last_seen": utc_now(),
            "fingerprint": fingerprint,
            "threshold": self.threshold,
            "feedback": {"accepted": 0, "rejected": 0},
        }
        self.save(registry)
        collection.upsert(
            ids=[new_id],
            documents=[fingerprint["identity_text"]],
            metadatas=[{"project_id": new_id, "name": fingerprint["name"], "root": str(root.resolve())}],
        )
        return ProjectDetectionResult(
            project_id=new_id,
            project_name=fingerprint["name"],
            confidence=1.0,
            is_new=True,
            scores={"structure_score": 0.0, "dependency_score": 0.0, "embedding_similarity": 0.0, "git_signal": 0.0, "total": 1.0},
            root=str(root.resolve()),
        )

    def feedback(self, project_id: str, correct: bool, notes: str | None = None) -> dict[str, Any]:
        registry = self.load()
        project = registry["projects"].get(project_id)
        if not project:
            return {"updated": False}
        bucket = "accepted" if correct else "rejected"
        project.setdefault("feedback", {"accepted": 0, "rejected": 0})
        project["feedback"][bucket] = int(project["feedback"].get(bucket, 0)) + 1
        if not correct:
            project["threshold"] = min(0.95, float(project.get("threshold", self.threshold)) + 0.02)
        else:
            project["threshold"] = max(0.75, float(project.get("threshold", self.threshold)) - 0.005)
        registry["feedback"].append({"project_id": project_id, "correct": correct, "notes": notes, "at": utc_now()})
        self.save(registry)
        return {"updated": True, "project": project}
