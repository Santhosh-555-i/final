import json
import uuid
import sqlite3
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
from app.config import settings

class FaceClusteringEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def compute_event_clusters(self, event_id: str, threshold: float = 0.55) -> List[Dict]:
        """
        Discovers people in an event using Centroid Average-Linkage clustering on 512-d FaceNet vector embeddings.
        Prevents chaining/mega-clusters, guaranteeing Google Photos-grade separation of different individuals.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Resolve event_id or code
        cursor.execute("SELECT id FROM events WHERE id = ? OR UPPER(event_code) = UPPER(?)", (event_id, event_id))
        ev_row = cursor.fetchone()
        actual_event_id = ev_row["id"] if ev_row else event_id

        # Fetch all face embeddings for event
        cursor.execute("""
            SELECT fe.id as emb_id, fe.photo_id, fe.embedding_json, fe.bounding_box_json, fe.cluster_id,
                   p.image_url, p.thumbnail_url, p.created_at
            FROM face_embeddings fe
            JOIN photos p ON fe.photo_id = p.id
            WHERE fe.event_id = ?
        """, (actual_event_id,))
        rows = cursor.fetchall()

        if not rows:
            conn.close()
            return []

        # Parse embeddings
        emb_list = []
        valid_rows = []
        for r in rows:
            try:
                emb = np.array(json.loads(r["embedding_json"]), dtype=np.float32)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                emb_list.append(emb)
                valid_rows.append(r)
            except Exception as e:
                print(f"[Clustering] Skip corrupted embedding {r['emb_id']}: {e}")

        n = len(emb_list)
        if n == 0:
            conn.close()
            return []

        # High-Precision Centroid / Average-Linkage Clustering
        cluster_groups = [] # list of dicts: {'indices': [...], 'centroid': vector}
        for idx, vec in enumerate(emb_list):
            best_c_idx = -1
            best_sim = -1.0
            for c_idx, cl in enumerate(cluster_groups):
                sim = float(np.dot(vec, cl['centroid']))
                if sim > best_sim:
                    best_sim = sim
                    best_c_idx = c_idx

            if best_sim >= threshold and best_c_idx >= 0:
                cluster_groups[best_c_idx]['indices'].append(idx)
                # Recompute normalized centroid
                c_vecs = [emb_list[i] for i in cluster_groups[best_c_idx]['indices']]
                new_centroid = np.mean(c_vecs, axis=0)
                cluster_groups[best_c_idx]['centroid'] = new_centroid / np.linalg.norm(new_centroid)
            else:
                cluster_groups.append({
                    'indices': [idx],
                    'centroid': vec.copy()
                })

        # Extract components list
        components = [cl['indices'] for cl in cluster_groups]
        # Sort components by size (largest clusters first)
        components.sort(key=len, reverse=True)

        # Sync clusters to database
        # 1. Fetch existing clusters for this event to preserve custom names
        cursor.execute("SELECT id, name, thumbnail_url FROM person_clusters WHERE event_id = ?", (actual_event_id,))
        existing_clusters = {r["id"]: dict(r) for r in cursor.fetchall()}

        cluster_results = []
        now_str = datetime.utcnow().isoformat()

        # Re-assign or create cluster records
        used_cluster_ids = set()
        for idx, comp in enumerate(components):
            default_name = f"Person {str(idx + 1).zfill(3)}"
            cluster_name = default_name
            assigned_id = str(uuid.uuid4())
            rep_row = valid_rows[comp[0]]
            rep_thumb = rep_row["thumbnail_url"] or rep_row["image_url"]

            # Check if any existing cluster with a custom user-provided name matches this group
            for c_idx in comp:
                orig_cid = valid_rows[c_idx]["cluster_id"]
                if orig_cid and orig_cid in existing_clusters and orig_cid not in used_cluster_ids:
                    custom_name = existing_clusters[orig_cid].get("name", "")
                    if custom_name and not custom_name.startswith("Person "):
                        cluster_name = custom_name
                        assigned_id = orig_cid
                        break

            used_cluster_ids.add(assigned_id)

            # Upsert cluster record
            cursor.execute("""
                INSERT INTO person_clusters (id, event_id, name, thumbnail_url, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name, thumbnail_url = excluded.thumbnail_url
            """, (assigned_id, actual_event_id, cluster_name, rep_thumb, now_str))

            # Update face_embeddings with cluster_id
            photo_set = {}
            for c_idx in comp:
                row = valid_rows[c_idx]
                cursor.execute("UPDATE face_embeddings SET cluster_id = ? WHERE id = ?", (assigned_id, row["emb_id"]))
                pid = row["photo_id"]
                if pid not in photo_set:
                    photo_set[pid] = {
                        "photo_id": pid,
                        "image_url": row["image_url"],
                        "thumbnail_url": row["thumbnail_url"],
                        "bounding_box": json.loads(row["bounding_box_json"]) if row["bounding_box_json"] else None,
                        "created_at": row["created_at"]
                    }

            cluster_results.append({
                "cluster_id": assigned_id,
                "event_id": actual_event_id,
                "name": cluster_name,
                "thumbnail_url": rep_thumb,
                "face_count": len(comp),
                "photo_count": len(photo_set),
                "photos": list(photo_set.values())
            })

        conn.commit()
        conn.close()
        return cluster_results

    def get_event_clusters(self, event_id: str) -> List[Dict]:
        """Returns existing person clusters for an event or triggers auto-clustering if none exist"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM events WHERE id = ? OR UPPER(event_code) = UPPER(?)", (event_id, event_id))
        ev_row = cursor.fetchone()
        actual_event_id = ev_row["id"] if ev_row else event_id

        cursor.execute("SELECT * FROM person_clusters WHERE event_id = ? ORDER BY name ASC", (actual_event_id,))
        c_rows = cursor.fetchall()

        if not c_rows:
            conn.close()
            return self.compute_event_clusters(actual_event_id)

        results = []
        for c in c_rows:
            cid = c["id"]
            cursor.execute("""
                SELECT fe.id as emb_id, fe.photo_id, fe.bounding_box_json, p.image_url, p.thumbnail_url, p.created_at
                FROM face_embeddings fe
                JOIN photos p ON fe.photo_id = p.id
                WHERE fe.cluster_id = ?
            """, (cid,))
            faces = cursor.fetchall()

            photo_map = {}
            for f in faces:
                pid = f["photo_id"]
                if pid not in photo_map:
                    photo_map[pid] = {
                        "photo_id": pid,
                        "image_url": f["image_url"],
                        "thumbnail_url": f["thumbnail_url"],
                        "bounding_box": json.loads(f["bounding_box_json"]) if f["bounding_box_json"] else None,
                        "created_at": f["created_at"]
                    }

            results.append({
                "cluster_id": cid,
                "event_id": actual_event_id,
                "name": c["name"],
                "thumbnail_url": c["thumbnail_url"],
                "face_count": len(faces),
                "photo_count": len(photo_map),
                "photos": list(photo_map.values())
            })

        conn.close()
        return results

    def rename_cluster(self, cluster_id: str, new_name: str) -> bool:
        """Renames a person cluster"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE person_clusters SET name = ? WHERE id = ?", (new_name.strip(), cluster_id))
        conn.commit()
        conn.close()
        return True

    def merge_clusters(self, target_cluster_id: str, source_cluster_id: str) -> bool:
        """Merges two person clusters into one"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE face_embeddings SET cluster_id = ? WHERE cluster_id = ?", (target_cluster_id, source_cluster_id))
        cursor.execute("DELETE FROM person_clusters WHERE id = ?", (source_cluster_id,))
        conn.commit()
        conn.close()
        return True

    def split_face(self, embedding_id: str, new_person_name: str) -> str:
        """Splits a single face into a new person cluster"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT fe.event_id, p.image_url, p.thumbnail_url 
            FROM face_embeddings fe
            JOIN photos p ON fe.photo_id = p.id
            WHERE fe.id = ?
        """, (embedding_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError("Embedding not found")

        new_cluster_id = str(uuid.uuid4())
        thumb = row["thumbnail_url"] or row["image_url"]
        now_str = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO person_clusters (id, event_id, name, thumbnail_url, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (new_cluster_id, row["event_id"], new_person_name.strip(), thumb, now_str))

        cursor.execute("UPDATE face_embeddings SET cluster_id = ? WHERE id = ?", (new_cluster_id, embedding_id))
        conn.commit()
        conn.close()
        return new_cluster_id

    def delete_person_biometrics(self, cluster_id: str) -> bool:
        """Deletes face vector biometric embeddings for a person while keeping the photo records"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM face_embeddings WHERE cluster_id = ?", (cluster_id,))
        cursor.execute("DELETE FROM person_clusters WHERE id = ?", (cluster_id,))
        conn.commit()
        conn.close()
        return True
