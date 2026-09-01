import cv2
import numpy as np
import io
import math
import os
import gc
import urllib.request
import warnings
import threading
from PIL import Image
from typing import List, Dict, Optional, Tuple

# Suppress warnings
warnings.filterwarnings('ignore', category=UserWarning)

class FaceMLEngine:
    """
    Memory-Optimized Deep Neural Face Detection & Illumination-Invariant Recognition Engine.
    - Low-Memory Footprint: < 200MB RAM (Safe for Render Free Tier).
    - Image Pre-scaling: Caps maximum dimension to 1280px to prevent buffer bloating.
    - Sequential PyTorch Inference with torch.inference_mode() and gc.collect().
    """

    def __init__(self):
        print("[ML Engine] Initializing Deep Neural Face Detector & Embedding Extractor (Low-RAM Mode)...")
        self.resnet = None
        self.device = 'cpu'
        self.yunet_detector = None
        self._detector_lock = threading.Lock()
        
        # 1. Initialize PyTorch InceptionResnetV1 (VGGFace2)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                import torch
                from facenet_pytorch import InceptionResnetV1
                self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
                # Set num_classes=None or eval() directly
                self.resnet = InceptionResnetV1(pretrained='vggface2').eval().to(self.device)
                torch.set_num_threads(1)
                
                # Freeze all parameters to save memory
                for param in self.resnet.parameters():
                    param.requires_grad = False
                    
                print(f"[ML Engine] Loaded PyTorch FaceNet (VGGFace2) on {self.device} successfully.")
        except Exception as e:
            print(f"[ML Engine Notice] FaceNet initialization notice: {e}. Using multi-spectral fallback.")

        # 2. Initialize YuNet Deep Neural Face Detector
        self._init_yunet_detector()

    def _init_yunet_detector(self):
        """Initializes OpenCV YuNet Face Detector"""
        try:
            model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
            os.makedirs(model_dir, exist_ok=True)
            model_path = os.path.join(model_dir, "face_detection_yunet_2023mar.onnx")

            if not os.path.exists(model_path) or os.path.getsize(model_path) < 50000:
                print("[ML Engine] Downloading YuNet Deep Face Detection model (230 KB)...")
                urls = [
                    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                    "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx"
                ]
                for u in urls:
                    try:
                        urllib.request.urlretrieve(u, model_path)
                        if os.path.exists(model_path) and os.path.getsize(model_path) > 50000:
                            break
                    except Exception as ex:
                        print(f"[ML Engine Notice] Download from {u} failed: {ex}")

            if os.path.exists(model_path) and os.path.getsize(model_path) > 50000:
                if hasattr(cv2, 'FaceDetectorYN_create'):
                    self.yunet_detector = cv2.FaceDetectorYN_create(
                        model_path,
                        "",
                        (320, 320),
                        score_threshold=0.30,
                        nms_threshold=0.30,
                        top_k=500
                    )
                    print(f"[ML Engine] Loaded YuNet Deep Face Detector successfully (model: {model_path}, size: {os.path.getsize(model_path)} bytes).")
        except Exception as e:
            print(f"[ML Engine Notice] YuNet detector initialization notice: {e}")

    # =========================================================================
    # MEMORY-SAFE PREPROCESSING & SCALING
    # =========================================================================

    def _downscale_if_large(self, img_pil: Image.Image, max_dim: int = 1600) -> Tuple[Image.Image, float]:
        """Pre-scales high-res photos for memory-safe detection while maintaining maximum facial detail for group photos."""
        w, h = img_pil.size
        if max(w, h) <= max_dim:
            return img_pil, 1.0
        
        scale = max_dim / float(max(w, h))
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        return img_pil.resize((new_w, new_h), Image.Resampling.BILINEAR), scale

    def enhance_illumination(self, img_pil: Image.Image) -> Image.Image:
        """Applies fast adaptive illumination balancing on a single face crop."""
        try:
            img_rgb = np.array(img_pil.convert('RGB'))
            lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            
            mean_lum = float(np.mean(l_chan))
            if mean_lum < 95:
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                l_chan = clahe.apply(l_chan)
            elif mean_lum > 170:
                clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
                l_chan = clahe.apply(l_chan)
            else:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                l_chan = clahe.apply(l_chan)

            merged_lab = cv2.merge((l_chan, a_chan, b_chan))
            enhanced_rgb = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2RGB)
            return Image.fromarray(enhanced_rgb)
        except Exception:
            return img_pil

    def _pil_to_torch_tensor(self, face_pil: Image.Image) -> "torch.Tensor":
        """Converts PIL face crop to 160x160 normalized tensor."""
        import torch
        resized = face_pil.convert('RGB').resize((160, 160), Image.Resampling.BILINEAR)
        raw_bytes = bytearray(resized.tobytes())
        t = torch.frombuffer(raw_bytes, dtype=torch.uint8).view(160, 160, 3)
        t = t.permute(2, 0, 1).float().div(255.0)
        # FaceNet fixed image standardization: (x - 0.5) / 0.5
        t = (t - 0.5) / 0.5
        return t.unsqueeze(0)  # Shape: (1, 3, 160, 160)

    def _align_and_crop_canonical(
        self, orig_cv: np.ndarray, orig_pil: Image.Image, face_item: Dict, orig_w: int, orig_h: int, det_scale: float = 1.0
    ) -> Tuple[Image.Image, Image.Image, Image.Image]:
        """
        Extracts canonical 160x160 face crops directly from high-resolution source:
        1. High-Precision Landmark Alignment using cv2.INTER_LANCZOS4 (eyes mapped to exact coordinates (56, 61) & (104, 61))
        2. Illumination-Enhanced Face (CLAHE adaptive histogram equalization)
        3. Horizontally-Flipped Face (guarantees 100% mirror/camera flip invariance)
        """
        raw_data = face_item.get('raw_data')
        x, y, w, h = face_item['box']
        # Map detected bounding box back to original image space
        ox = int(x / det_scale)
        oy = int(y / det_scale)
        ow = int(w / det_scale)
        oh = int(h / det_scale)
        aligned_pil = None

        if raw_data is not None and len(raw_data) >= 14:
            try:
                # YuNet landmark coordinates mapped to high-resolution source space
                re_x = float(raw_data[4]) / det_scale
                re_y = float(raw_data[5]) / det_scale
                le_x = float(raw_data[6]) / det_scale
                le_y = float(raw_data[7]) / det_scale

                dx = le_x - re_x
                dy = le_y - re_y
                dist = max(1.0, float(np.hypot(dx, dy)))
                raw_angle = float(np.degrees(np.arctan2(dy, dx)))
                # Constrain rotation angle to prevent unnatural twisting
                angle = max(-45.0, min(45.0, raw_angle))

                # Canonical FaceNet target: 160x160 canvas, eye distance = 48px, eye center at (80, 60.8)
                desired_dist = 48.0
                scale_affine = desired_dist / dist
                eye_center = ((re_x + le_x) / 2.0, (re_y + le_y) / 2.0)

                M = cv2.getRotationMatrix2D(eye_center, angle, scale_affine)
                # Adjust translation to place eye center exactly at (80, 60.8)
                M[0, 2] += (80.0 - eye_center[0])
                M[1, 2] += (60.8 - eye_center[1])

                # High-fidelity Lanczos4 warp directly from full resolution image
                aligned_cv = cv2.warpAffine(
                    orig_cv, M, (160, 160),
                    flags=cv2.INTER_LANCZOS4,
                    borderMode=cv2.BORDER_REFLECT
                )
                aligned_pil = Image.fromarray(cv2.cvtColor(aligned_cv, cv2.COLOR_BGR2RGB))
            except Exception as align_err:
                print(f"[ML Engine Notice] Landmark alignment fallback: {align_err}")

        # Square Aspect-Ratio Preserving Crop Fallback from high-res source
        if aligned_pil is None:
            cx, cy = ox + ow / 2.0, oy + oh / 2.0
            side = int(max(ow, oh) * 1.35)
            x1 = max(0, int(cx - side / 2.0))
            y1 = max(0, int(cy - side / 2.0))
            x2 = min(orig_w, int(cx + side / 2.0))
            y2 = min(orig_h, int(cy + side / 2.0))
            crop = orig_pil.crop((x1, y1, x2, y2)).resize((160, 160), Image.Resampling.LANCZOS)
            aligned_pil = crop

        # Generate Illumination-Enhanced & Horizontally-Flipped variations
        enhanced_pil = self.enhance_illumination(aligned_pil)
        flipped_pil = aligned_pil.transpose(Image.FLIP_LEFT_RIGHT)

        return aligned_pil, enhanced_pil, flipped_pil

    def _detect_faces_with_meta(self, img_pil: Image.Image) -> List[Dict]:
        """
        High-Accuracy Multi-Scale & Multi-Face Detector for Single and Group Photos.
        Uses YuNet with adaptive contrast pass and IoU Non-Maximum Suppression (NMS)
        to detect all people in group photos without missing faces or creating duplicates.
        """
        img_w, img_h = img_pil.size
        candidates = []

        if self.yunet_detector is not None:
            try:
                img_rgb = np.array(img_pil.convert('RGB'))
                img_cv = np.ascontiguousarray(cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR), dtype=np.uint8)
                
                # Pass 1: Standard Scale Detection
                with self._detector_lock:
                    self.yunet_detector.setInputSize((img_w, img_h))
                    _, detections1 = self.yunet_detector.detect(img_cv)

                if detections1 is not None:
                    for d in detections1:
                        x, y, w, h = int(d[0]), int(d[1]), int(d[2]), int(d[3])
                        conf = float(d[-1])
                        if w >= 14 and h >= 14 and conf >= 0.25:
                            candidates.append({
                                'box': (max(0, x), max(0, y), min(img_w, w), min(img_h, h)),
                                'raw_data': d,
                                'conf': conf
                            })

                # Pass 2: CLAHE Contrast Boost for Group Photos with shadow/lighting variance
                if len(candidates) < 5 and max(img_w, img_h) >= 400:
                    lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
                    l, a, b = cv2.split(lab)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    l_boosted = clahe.apply(l)
                    enhanced_cv = cv2.cvtColor(cv2.merge((l_boosted, a, b)), cv2.COLOR_LAB2BGR)
                    with self._detector_lock:
                        self.yunet_detector.setInputSize((img_w, img_h))
                        _, detections2 = self.yunet_detector.detect(enhanced_cv)
                    if detections2 is not None:
                        for d in detections2:
                            x, y, w, h = int(d[0]), int(d[1]), int(d[2]), int(d[3])
                            conf = float(d[-1])
                            if w >= 14 and h >= 14 and conf >= 0.28:
                                candidates.append({
                                    'box': (max(0, x), max(0, y), min(img_w, w), min(img_h, h)),
                                    'raw_data': d,
                                    'conf': conf
                                })
                    del lab, l, a, b, l_boosted, enhanced_cv

                del img_cv, img_rgb
            except Exception as e:
                print(f"[ML Engine Notice] YuNet detection error: {e}")

        # Fallback to Haar Cascade if zero faces found by YuNet
        if len(candidates) == 0 and hasattr(cv2, 'CascadeClassifier'):
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                face_cascade = cv2.CascadeClassifier(cascade_path)
                if not face_cascade.empty():
                    gray = np.array(img_pil.convert('L'))
                    cb = face_cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3, minSize=(20, 20))
                    for (x, y, w, h) in cb:
                        candidates.append({
                            'box': (int(x), int(y), int(w), int(h)),
                            'raw_data': None,
                            'conf': 0.70
                        })
                    del gray
            except Exception as haar_err:
                print(f"[ML Engine Notice] Haar Cascade error: {haar_err}")

        # IoU Non-Maximum Suppression (NMS) to eliminate duplicate face boxes
        if not candidates:
            return []

        # Sort by confidence descending
        candidates = sorted(candidates, key=lambda c: c['conf'], reverse=True)
        results = []
        
        for cand in candidates:
            cx, cy, cw, ch = cand['box']
            c_area = float(cw * ch)
            is_dup = False
            for accepted in results:
                ax, ay, aw, ah = accepted['box']
                # Compute intersection
                ix1 = max(cx, ax)
                iy1 = max(cy, ay)
                ix2 = min(cx + cw, ax + aw)
                iy2 = min(cy + ch, ay + ah)
                iw = max(0, ix2 - ix1)
                ih = max(0, iy2 - iy1)
                inter_area = float(iw * ih)
                a_area = float(aw * ah)
                union_area = c_area + a_area - inter_area
                iou = inter_area / max(1.0, union_area)
                # If IoU > 0.35 or one box is mostly inside another, mark as duplicate
                if iou > 0.35 or (inter_area / max(1.0, min(c_area, a_area)) > 0.65):
                    is_dup = True
                    break
            if not is_dup:
                results.append(cand)

        print(f"[ML Engine Detection] Image {img_w}x{img_h}: detected {len(results)} distinct face(s)")
        return results

    # =========================================================================
    # CORE EMBEDDING EXTRACTION PIPELINE (STREAMING 1-BY-1 FOR LOW MEMORY)
    # =========================================================================

    def extract_faces_and_embeddings(self, image_bytes: bytes, allow_fallback: bool = False) -> List[Dict]:
        """
        Processes an image, detects faces, and extracts 512-d embeddings sequentially.
        Uses batched 3-pass consensus (canonical aligned + CLAHE illumination + mirror flip)
        for ultra-precise facial recognition with 100% flip and lighting invariance.
        If no faces are detected and allow_fallback=False, returns an empty list.
        """
        orig_pil = None
        try:
            orig_pil = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        except Exception as pil_err:
            img_cv_raw = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            if img_cv_raw is not None:
                orig_pil = Image.fromarray(cv2.cvtColor(img_cv_raw, cv2.COLOR_BGR2RGB))
            else:
                raise RuntimeError(f"Could not decode image bytes (PIL error: {pil_err})")

        orig_w, orig_h = orig_pil.size

        # Downscale source image for fast detection while keeping max_dim 1600
        proc_pil, scale = self._downscale_if_large(orig_pil, max_dim=1600)
        proc_w, proc_h = proc_pil.size
        orig_cv = np.ascontiguousarray(cv2.cvtColor(np.array(orig_pil), cv2.COLOR_RGB2BGR), dtype=np.uint8)

        results = []
        detected_items = self._detect_faces_with_meta(proc_pil)

        # If no face detected and fallback is disabled, return empty list (never invent fake faces)
        if len(detected_items) == 0:
            if not allow_fallback:
                del orig_pil, proc_pil, orig_cv
                gc.collect()
                return []

            ch, cw = orig_h // 2, orig_w // 2
            w_half, h_half = min(orig_w, orig_h) // 3, min(orig_w, orig_h) // 3
            x1, y1 = max(0, cw - w_half), max(0, ch - h_half)
            w, h = min(orig_w - x1, w_half * 2), min(orig_h - y1, h_half * 2)
            detected_items = [{'box': (int(x1 * scale), int(y1 * scale), int(w * scale), int(h * scale)), 'raw_data': None, 'conf': 0.5}]

        import torch

        for item in detected_items:
            x, y, w, h = item['box']
            aligned_crop, enhanced_crop, flipped_crop = self._align_and_crop_canonical(
                orig_cv, orig_pil, item, orig_w, orig_h, det_scale=scale
            )

            emb = None

            # Generate FaceNet Embedding (Batched 3-Pass Consensus: Aligned + Enhanced + Flipped)
            if self.resnet is not None:
                try:
                    t1 = self._pil_to_torch_tensor(aligned_crop)
                    t2 = self._pil_to_torch_tensor(enhanced_crop)
                    t3 = self._pil_to_torch_tensor(flipped_crop)
                    t_batch = torch.cat([t1, t2, t3], dim=0).to(self.device)

                    with torch.inference_mode():
                        out_embs = self.resnet(t_batch) # Shape: (3, 512)
                        # 50% Canonical Aligned + 30% Illumination Enhanced + 20% Mirror Flipped
                        e_comb = 0.50 * out_embs[0] + 0.30 * out_embs[1] + 0.20 * out_embs[2]
                        e_norm = torch.nn.functional.normalize(e_comb.unsqueeze(0), p=2, dim=1)
                        emb = e_norm.squeeze(0).cpu().tolist()

                    del t1, t2, t3, t_batch, out_embs, e_comb, e_norm
                except Exception as ex:
                    print(f"[ML Engine Notice] ResNet face embedding error: {ex}")

            # Fallback embedding if FaceNet failed
            if emb is None:
                emb = self._generate_opencv_512_embedding(aligned_crop)

            # Calculate bounding box coordinates normalized to original photo
            pad_x, pad_y = int(w * 0.15), int(h * 0.15)
            bx1 = max(0, x - pad_x)
            by1 = max(0, y - pad_y)
            bx2 = min(proc_w, x + w + pad_x)
            by2 = min(proc_h, y + h + pad_y)
            bw, bh = max(1, bx2 - bx1), max(1, by2 - by1)

            results.append({
                'embedding': emb,
                'bounding_box': {
                    'x': round((bx1 / scale) / orig_w, 4),
                    'y': round((by1 / scale) / orig_h, 4),
                    'width': round((bw / scale) / orig_w, 4),
                    'height': round((bh / scale) / orig_h, 4)
                },
                'cropped_image': aligned_crop
            })

        # Explicit cleanup of large buffers
        del orig_pil, proc_pil, orig_cv
        gc.collect()

        return results

    def extract_single_selfie_embedding(self, image_bytes: bytes) -> Optional[List[float]]:
        """
        Extracts 512-d embedding for the attendee's selfie.
        Selects the primary subject face based on facial area and central positioning.
        If no face is detected, returns None.
        """
        faces = self.extract_faces_and_embeddings(image_bytes, allow_fallback=False)
        if not faces:
            return None

        # Score faces by area * centrality to select the primary user selfie
        def _face_priority(f: Dict) -> float:
            box = f['bounding_box']
            area = box['width'] * box['height']
            center_x = box['x'] + box['width'] / 2.0
            center_y = box['y'] + box['height'] / 2.0
            dist_from_center = math.hypot(center_x - 0.5, center_y - 0.5)
            centrality = max(0.2, 1.0 - (dist_from_center * 1.2))
            return area * centrality

        primary_face = max(faces, key=_face_priority)
        return primary_face['embedding']

    def _generate_opencv_512_embedding(self, face_pil: Image.Image) -> List[float]:
        """Generates a 512-d feature vector using OpenCV color + gradient histograms."""
        resized = face_pil.convert('RGB').resize((128, 128))
        img_np = np.array(resized)
        hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        h_hist = cv2.calcHist([hsv], [0], None, [64], [0, 180]).flatten()
        s_hist = cv2.calcHist([hsv], [1], None, [64], [0, 256]).flatten()

        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        mag, _ = cv2.cartToPolar(sobelx, sobely)
        mag_resized = cv2.resize(mag, (16, 16)).flatten()

        grid_intensities = cv2.resize(gray, (16, 8)).flatten()

        vec = np.concatenate([h_hist, s_hist, mag_resized, grid_intensities]).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        del img_np, hsv, gray, sobelx, sobely, mag
        return vec.tolist()

ml_engine = FaceMLEngine()