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

    def _get_supabase(self):
        from app.database import db_service
        return db_service.supabase

    def compute_event_clusters(self, event_id: str, threshold: float = 0.55) -> List[Dict]:
        actual_event_id = event_id
        
        # 1. Fetch data
        if settings.DB_MODE == "supabase":
            supabase = self._get_supabase()
            ev_res = supabase.table("events").select("id").or_(f"id.eq.{event_id},event_code.ilike.{event_id}").limit(1).execute()
            if ev_res.data:
                actual_event_id = ev_res.data[0]["id"]

            emb_res = supabase.table("face_embeddings").select(
                "id, photo_id, embedding, bounding_box, cluster_id, photos(image_url, thumbnail_url, created_at)"
            ).eq("event_id", actual_event_id).execute()
            
            rows = []
            for r in (emb_res.data or []):
                p = r.get("photos", {})
                rows.append({
                    "emb_id": r["id"],
                    "photo_id": r["photo_id"],
                    "embedding": r["embedding"],
                    "bounding_box_json": r["bounding_box"],
                    "cluster_id": r["cluster_id"],
                    "image_url": p.get("image_url"),
                    "thumbnail_url": p.get("thumbnail_url"),
                    "created_at": p.get("created_at")
                })
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM events WHERE id = ? OR UPPER(event_code) = UPPER(?)", (event_id, event_id))
            ev_row = cursor.fetchone()
            if ev_row:
                actual_event_id = ev_row["id"]
            cursor.execute("""
                SELECT fe.id as emb_id, fe.photo_id, fe.embedding_json as embedding, fe.bounding_box_json, fe.cluster_id,
                       p.image_url, p.thumbnail_url, p.created_at
                FROM face_embeddings fe
                JOIN photos p ON fe.photo_id = p.id
                WHERE fe.event_id = ?
            """, (actual_event_id,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()

        if not rows:
            return []

        # Parse embeddings
        emb_list = []
        valid_rows = []
        for r in rows:
            try:
                emb = r["embedding"]
                if isinstance(emb, str):
                    emb = json.loads(emb)
                emb = np.array(emb, dtype=np.float32)
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                emb_list.append(emb)
                valid_rows.append(r)
            except Exception as e:
                print(f"[Clustering] Skip corrupted embedding {r['emb_id']}: {e}")

        n = len(emb_list)
        if n == 0:
            return []

        cluster_groups = []
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
                c_vecs = [emb_list[i] for i in cluster_groups[best_c_idx]['indices']]
                new_centroid = np.mean(c_vecs, axis=0)
                cluster_groups[best_c_idx]['centroid'] = new_centroid / np.linalg.norm(new_centroid)
            else:
                cluster_groups.append({'indices': [idx], 'centroid': vec.copy()})

        components = [cl['indices'] for cl in cluster_groups]
        components.sort(key=len, reverse=True)

        existing_clusters = {}
        if settings.DB_MODE == "supabase":
            c_res = supabase.table("person_clusters").select("id, name, thumbnail_url").eq("event_id", actual_event_id).execute()
            for r in (c_res.data or []):
                existing_clusters[r["id"]] = r
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, thumbnail_url FROM person_clusters WHERE event_id = ?", (actual_event_id,))
            for r in cursor.fetchall():
                existing_clusters[r["id"]] = dict(r)
            conn.close()

        cluster_results = []
        now_str = datetime.utcnow().isoformat()
        used_cluster_ids = set()

        for idx, comp in enumerate(components):
            default_name = f"Person {str(idx + 1).zfill(3)}"
            cluster_name = default_name
            assigned_id = str(uuid.uuid4())
            rep_row = valid_rows[comp[0]]
            rep_thumb = rep_row["thumbnail_url"] or rep_row["image_url"]

            for c_idx in comp:
                orig_cid = valid_rows[c_idx]["cluster_id"]
                if orig_cid and orig_cid in existing_clusters and orig_cid not in used_cluster_ids:
                    custom_name = existing_clusters[orig_cid].get("name", "")
                    if custom_name and not custom_name.startswith("Person "):
                        cluster_name = custom_name
                        assigned_id = orig_cid
                        break

            used_cluster_ids.add(assigned_id)

            photo_set = {}
            for c_idx in comp:
                row = valid_rows[c_idx]
                pid = row["photo_id"]
                if pid not in photo_set:
                    bbox = row["bounding_box_json"]
                    if isinstance(bbox, str):
                        bbox = json.loads(bbox)
                    photo_set[pid] = {
                        "photo_id": pid,
                        "image_url": row["image_url"],
                        "thumbnail_url": row["thumbnail_url"],
                        "bounding_box": bbox,
                        "created_at": row["created_at"]
                    }

            if settings.DB_MODE == "supabase":
                supabase.table("person_clusters").upsert({
                    "id": assigned_id,
                    "event_id": actual_event_id,
                    "name": cluster_name,
                    "thumbnail_url": rep_thumb,
                    "created_at": now_str
                }).execute()
                for c_idx in comp:
                    supabase.table("face_embeddings").update({"cluster_id": assigned_id}).eq("id", valid_rows[c_idx]["emb_id"]).execute()
            else:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO person_clusters (id, event_id, name, thumbnail_url, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET name = excluded.name, thumbnail_url = excluded.thumbnail_url
                """, (assigned_id, actual_event_id, cluster_name, rep_thumb, now_str))
                for c_idx in comp:
                    cursor.execute("UPDATE face_embeddings SET cluster_id = ? WHERE id = ?", (assigned_id, valid_rows[c_idx]["emb_id"]))
                conn.commit()
                conn.close()

            cluster_results.append({
                "cluster_id": assigned_id,
                "event_id": actual_event_id,
                "name": cluster_name,
                "thumbnail_url": rep_thumb,
                "face_count": len(comp),
                "photo_count": len(photo_set),
                "photos": list(photo_set.values())
            })

        return cluster_results

    def get_event_clusters(self, event_id: str) -> List[Dict]:
        actual_event_id = event_id
        if settings.DB_MODE == "supabase":
            supabase = self._get_supabase()
            ev_res = supabase.table("events").select("id").or_(f"id.eq.{event_id},event_code.ilike.{event_id}").limit(1).execute()
            if ev_res.data:
                actual_event_id = ev_res.data[0]["id"]
            
            c_res = supabase.table("person_clusters").select("*").eq("event_id", actual_event_id).order("name").execute()
            c_rows = c_res.data or []
            if not c_rows:
                return self.compute_event_clusters(actual_event_id)

            results = []
            for c in c_rows:
                cid = c["id"]
                faces_res = supabase.table("face_embeddings").select("id, photo_id, bounding_box, photos(image_url, thumbnail_url, created_at)").eq("cluster_id", cid).execute()
                
                photo_map = {}
                faces = faces_res.data or []
                for f in faces:
                    pid = f["photo_id"]
                    p = f.get("photos", {})
                    if pid not in photo_map:
                        bbox = f["bounding_box"]
                        if isinstance(bbox, str):
                            bbox = json.loads(bbox)
                        photo_map[pid] = {
                            "photo_id": pid,
                            "image_url": p.get("image_url"),
                            "thumbnail_url": p.get("thumbnail_url"),
                            "bounding_box": bbox,
                            "created_at": p.get("created_at")
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
            return results
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM events WHERE id = ? OR UPPER(event_code) = UPPER(?)", (event_id, event_id))
            ev_row = cursor.fetchone()
            if ev_row:
                actual_event_id = ev_row["id"]

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
        if settings.DB_MODE == "supabase":
            self._get_supabase().table("person_clusters").update({"name": new_name.strip()}).eq("id", cluster_id).execute()
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE person_clusters SET name = ? WHERE id = ?", (new_name.strip(), cluster_id))
            conn.commit()
            conn.close()
        return True

    def merge_clusters(self, target_cluster_id: str, source_cluster_id: str) -> bool:
        if settings.DB_MODE == "supabase":
            supabase = self._get_supabase()
            supabase.table("face_embeddings").update({"cluster_id": target_cluster_id}).eq("cluster_id", source_cluster_id).execute()
            supabase.table("person_clusters").delete().eq("id", source_cluster_id).execute()
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE face_embeddings SET cluster_id = ? WHERE cluster_id = ?", (target_cluster_id, source_cluster_id))
            cursor.execute("DELETE FROM person_clusters WHERE id = ?", (source_cluster_id,))
            conn.commit()
            conn.close()
        return True

    def split_face(self, embedding_id: str, new_person_name: str) -> str:
        new_cluster_id = str(uuid.uuid4())
        now_str = datetime.utcnow().isoformat()
        
        if settings.DB_MODE == "supabase":
            supabase = self._get_supabase()
            fe_res = supabase.table("face_embeddings").select("event_id, photos(image_url, thumbnail_url)").eq("id", embedding_id).single().execute()
            if not fe_res.data:
                raise ValueError("Embedding not found")
            
            row = fe_res.data
            p = row.get("photos", {})
            thumb = p.get("thumbnail_url") or p.get("image_url")
            
            supabase.table("person_clusters").insert({
                "id": new_cluster_id,
                "event_id": row["event_id"],
                "name": new_person_name.strip(),
                "thumbnail_url": thumb,
                "created_at": now_str
            }).execute()
            
            supabase.table("face_embeddings").update({"cluster_id": new_cluster_id}).eq("id", embedding_id).execute()
            return new_cluster_id
        else:
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

            thumb = row["thumbnail_url"] or row["image_url"]
            cursor.execute("""
                INSERT INTO person_clusters (id, event_id, name, thumbnail_url, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (new_cluster_id, row["event_id"], new_person_name.strip(), thumb, now_str))

            cursor.execute("UPDATE face_embeddings SET cluster_id = ? WHERE id = ?", (new_cluster_id, embedding_id))
            conn.commit()
            conn.close()
            return new_cluster_id

    def delete_person_biometrics(self, cluster_id: str) -> bool:
        if settings.DB_MODE == "supabase":
            supabase = self._get_supabase()
            supabase.table("face_embeddings").delete().eq("cluster_id", cluster_id).execute()
            supabase.table("person_clusters").delete().eq("id", cluster_id).execute()
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM face_embeddings WHERE cluster_id = ?", (cluster_id,))
            cursor.execute("DELETE FROM person_clusters WHERE id = ?", (cluster_id,))
            conn.commit()
            conn.close()
        return True
