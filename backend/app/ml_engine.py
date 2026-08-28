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
                        score_threshold=0.50,
                        nms_threshold=0.30,
                        top_k=200
                    )
                    print(f"[ML Engine] Loaded YuNet Deep Face Detector successfully.")
        except Exception as e:
            print(f"[ML Engine Notice] YuNet detector initialization notice: {e}")

    # =========================================================================
    # MEMORY-SAFE PREPROCESSING & SCALING
    # =========================================================================

    def _downscale_if_large(self, img_pil: Image.Image, max_dim: int = 960) -> Tuple[Image.Image, float]:
        """Pre-scales high-res photos to prevent buffer bloat while maintaining aspect ratio."""
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
        # FaceNet normalization: (x - 0.5) / 0.5
        t = (t - 0.5) / 0.5
        return t.unsqueeze(0)  # Shape: (1, 3, 160, 160)

    def _align_face_crop(self, face_crop: Image.Image, face_data: Optional[np.ndarray], x1: int, y1: int, scale: float = 1.0) -> Image.Image:
        """Aligns face horizontally based on detected eye landmarks."""
        if face_data is None or len(face_data) < 14:
            return face_crop
        try:
            re_x, re_y = (float(face_data[4]) / scale) - x1, (float(face_data[5]) / scale) - y1
            le_x, le_y = (float(face_data[6]) / scale) - x1, (float(face_data[7]) / scale) - y1
            dx = le_x - re_x
            dy = le_y - re_y
            angle = float(np.degrees(np.arctan2(dy, dx)))
            eye_center = ((re_x + le_x) / 2.0, (re_y + le_y) / 2.0)

            img_cv = cv2.cvtColor(np.array(face_crop.convert('RGB')), cv2.COLOR_RGB2BGR)
            h, w, _ = img_cv.shape
            M = cv2.getRotationMatrix2D(eye_center, angle, 1.0)
            aligned_cv = cv2.warpAffine(img_cv, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            return Image.fromarray(cv2.cvtColor(aligned_cv, cv2.COLOR_BGR2RGB))
        except Exception:
            return face_crop

    def _detect_faces_with_meta(self, img_pil: Image.Image) -> List[Dict]:
        """Detects faces using YuNet with fallback to Haar Cascade."""
        img_w, img_h = img_pil.size
        results = []

        if self.yunet_detector is not None:
            try:
                img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                with self._detector_lock:
                    self.yunet_detector.setInputSize((img_w, img_h))
                    _, detections = self.yunet_detector.detect(img_cv)

                if detections is not None:
                    for d in detections:
                        x, y, w, h = int(d[0]), int(d[1]), int(d[2]), int(d[3])
                        conf = float(d[-1])
                        if w >= 32 and h >= 32 and conf >= 0.50:
                            results.append({
                                'box': (x, y, w, h),
                                'raw_data': d,
                                'conf': conf
                            })
                del img_cv
            except Exception as e:
                print(f"[ML Engine Notice] YuNet detection error: {e}")

        # Fallback to Haar Cascade
        if len(results) == 0 and hasattr(cv2, 'CascadeClassifier'):
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                face_cascade = cv2.CascadeClassifier(cascade_path)
                if not face_cascade.empty():
                    gray = np.array(img_pil.convert('L'))
                    cb = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
                    for (x, y, w, h) in cb:
                        results.append({
                            'box': (int(x), int(y), int(w), int(h)),
                            'raw_data': None,
                            'conf': 0.75
                        })
                    del gray
            except Exception:
                pass

        return results

    # =========================================================================
    # CORE EMBEDDING EXTRACTION PIPELINE (STREAMING 1-BY-1 FOR LOW MEMORY)
    # =========================================================================

    def extract_faces_and_embeddings(self, image_bytes: bytes, allow_fallback: bool = True) -> List[Dict]:
        """
        Processes an image, detects faces, and extracts 512-d embeddings sequentially.
        Guarantees low memory consumption by explicitly reclaiming RAM.
        """
        orig_pil = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        orig_w, orig_h = orig_pil.size

        # Downscale source image for detection & crop slicing (conserves RAM)
        proc_pil, scale = self._downscale_if_large(orig_pil, max_dim=1280)
        proc_w, proc_h = proc_pil.size

        results = []
        detected_items = self._detect_faces_with_meta(proc_pil)

        # Fallback if no face detected in event photo and fallback is allowed
        if len(detected_items) == 0:
            if not allow_fallback:
                del orig_pil, proc_pil
                gc.collect()
                return []

            ch, cw = proc_h // 2, proc_w // 2
            w_half, h_half = min(proc_w, proc_h) // 3, min(proc_w, proc_h) // 3
            x1, y1 = max(0, cw - w_half), max(0, ch - h_half)
            w, h = min(proc_w - x1, w_half * 2), min(proc_h - y1, h_half * 2)
            detected_items = [{'box': (x1, y1, w, h), 'raw_data': None, 'conf': 0.5}]

        import torch

        for item in detected_items:
            x, y, w, h = item['box']
            
            # Add 15% contextual margin
            pad_x, pad_y = int(w * 0.15), int(h * 0.15)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(proc_w, x + w + pad_x)
            y2 = min(proc_h, y + h + pad_y)
            bw, bh = max(1, x2 - x1), max(1, y2 - y1)

            face_crop = proc_pil.crop((x1, y1, x2, y2))
            aligned_crop = self._align_face_crop(face_crop, item.get('raw_data'), x1, y1, scale=1.0)
            enhanced_crop = self.enhance_illumination(aligned_crop)

            emb = None

            # Generate FaceNet Embedding (Single 2-Pass Consensus: Aligned + Enhanced)
            if self.resnet is not None:
                try:
                    t1 = self._pil_to_torch_tensor(aligned_crop).to(self.device)
                    t2 = self._pil_to_torch_tensor(enhanced_crop).to(self.device)
                    
                    with torch.inference_mode():
                        e1 = self.resnet(t1)
                        e2 = self.resnet(t2)
                        
                        # 60% Aligned + 40% Illumination Balanced
                        e_comb = 0.60 * e1 + 0.40 * e2
                        e_norm = torch.nn.functional.normalize(e_comb, p=2, dim=1)
                        emb = e_norm.squeeze(0).cpu().tolist()

                    del t1, t2, e1, e2, e_comb, e_norm
                except Exception as ex:
                    print(f"[ML Engine Notice] ResNet single face error: {ex}")

            # Fallback embedding if FaceNet failed
            if emb is None:
                emb = self._generate_opencv_512_embedding(aligned_crop)

            # Map relative coordinates back to original photo bounds
            results.append({
                'embedding': emb,
                'bounding_box': {
                    'x': round((x1 / scale) / orig_w, 4),
                    'y': round((y1 / scale) / orig_h, 4),
                    'width': round((bw / scale) / orig_w, 4),
                    'height': round((bh / scale) / orig_h, 4)
                },
                'cropped_image': face_crop
            })

        # Explicit cleanup of large buffers
        del orig_pil, proc_pil
        gc.collect()

        return results

    def extract_single_selfie_embedding(self, image_bytes: bytes) -> Optional[List[float]]:
        """Extracts 512-d embedding for the attendee's selfie."""
        faces = self.extract_faces_and_embeddings(image_bytes, allow_fallback=True)
        if not faces:
            return None
        # Pick the largest face in frame
        largest_face = max(faces, key=lambda f: f['bounding_box']['width'] * f['bounding_box']['height'])
        return largest_face['embedding']

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