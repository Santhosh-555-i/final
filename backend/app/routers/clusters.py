from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.clustering import FaceClusteringEngine
from app.database import db_service
from app.config import settings
from app.routers.auth import get_current_admin

router = APIRouter(prefix="/clusters", tags=["Person Discovery & Clusters"])
clustering_engine = FaceClusteringEngine(
    db_service.db_path if settings.DB_MODE == "sqlite" else None
)

class RenameClusterRequest(BaseModel):
    name: str

class MergeClusterRequest(BaseModel):
    target_cluster_id: str
    source_cluster_id: str

class SplitFaceRequest(BaseModel):
    embedding_id: str
    new_person_name: str

@router.get("/event/{event_id}")
def get_event_clusters(event_id: str):
    """
    Returns discovered people clusters for an event.
    Automatically runs agglomerative face clustering if none exist yet.
    """
    try:
        clusters = clustering_engine.get_event_clusters(event_id)
        return {"success": True, "count": len(clusters), "clusters": clusters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/event/{event_id}/recluster")
def recompute_event_clusters(event_id: str, threshold: float = 0.55, admin_email: str = Depends(get_current_admin)):
    """
    Forces a complete re-clustering of all face embeddings in the event.
    """
    try:
        clusters = clustering_engine.compute_event_clusters(event_id, threshold=threshold)
        db_service.log_audit_action(event_id, "RECOMPUTE_CLUSTERS", {"threshold": threshold, "cluster_count": len(clusters)})
        return {"success": True, "count": len(clusters), "clusters": clusters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{cluster_id}/name")
def rename_cluster(cluster_id: str, req: RenameClusterRequest, admin_email: str = Depends(get_current_admin)):
    """
    Renames a discovered person cluster (e.g. 'Person 001' -> 'Alice Smith').
    """
    try:
        clustering_engine.rename_cluster(cluster_id, req.name)
        return {"success": True, "message": f"Cluster renamed to {req.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/merge")
def merge_clusters(req: MergeClusterRequest, admin_email: str = Depends(get_current_admin)):
    """
    Merges two person clusters into one.
    """
    try:
        clustering_engine.merge_clusters(req.target_cluster_id, req.source_cluster_id)
        db_service.log_audit_action(None, "MERGE_CLUSTERS", {"target": req.target_cluster_id, "source": req.source_cluster_id})
        return {"success": True, "message": "Clusters merged successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/split")
def split_face(req: SplitFaceRequest, admin_email: str = Depends(get_current_admin)):
    """
    Splits a single face out of a cluster into a new individual person profile.
    """
    try:
        new_cid = clustering_engine.split_face(req.embedding_id, req.new_person_name)
        return {"success": True, "new_cluster_id": new_cid, "message": f"Split into '{req.new_person_name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{cluster_id}/biometrics")
def delete_person_biometrics(cluster_id: str, admin_email: str = Depends(get_current_admin)):
    """
    Deletes all biometric face embeddings for a specific person cluster (GDPR compliance).
    """
    try:
        clustering_engine.delete_person_biometrics(cluster_id)
        db_service.log_audit_action(None, "DELETE_PERSON_BIOMETRICS", {"cluster_id": cluster_id})
        return {"success": True, "message": "Biometric data for person deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
