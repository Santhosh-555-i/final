from app.routers.clusters import clustering_engine
from app.database import db_service

event = db_service.get_event_by_code('TESTDRIVE14')
if event:
    print('Event:', event['id'])
    clusters = clustering_engine.get_event_clusters(event['id'])
    print(f'Retrieved {len(clusters)} person clusters!')
    for c in clusters:
        print(f" - Person: {c['name']} | Photos: {c['photo_count']} | Faces: {c['face_count']}")
else:
    print("Event not found.")
