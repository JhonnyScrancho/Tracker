import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re
import cv2
import numpy as np
import streamlit as st
from typing import Optional, List

class PlateDetector:
    def __init__(self):
        """Initialize detector with multiple lightweight OCR libraries"""
        self.tesseract_config = '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        
        # Check library availability without crashing
        self.cv2_available = self._check_cv2()
        self.pyzbar_available = self._check_pyzbar()
        self.textract_available = self._check_textract()
        self.kraken_available = self._check_kraken()
        
    @staticmethod
    def _check_cv2():
        try:
            import cv2
            return True
        except ImportError:
            st.warning("OpenCV not available - some preprocessing features will be limited")
            return False
            
    @staticmethod
    def _check_pyzbar():
        try:
            from pyzbar.pyzbar import decode
            return True
        except ImportError:
            st.warning("pyzbar not available - QR/barcode detection disabled")
            return False
            
    @staticmethod
    def _check_textract():
        try:
            import textract
            return True
        except ImportError:
            st.warning("textract not available - falling back to other OCR methods")
            return False
            
    @staticmethod
    def _check_kraken():
        try:
            import kraken
            return True
        except ImportError:
            st.warning("kraken not available - falling back to other OCR methods")
            return False

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image with error handling"""
        if not self.cv2_available:
            return image
            
        try:
            # Grayscale conversion
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Resize if too large
            height, width = gray.shape
            if width > 1000:
                scale = 1000 / width
                gray = cv2.resize(gray, None, fx=scale, fy=scale)
            
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(enhanced)
            
            # Adaptive thresholding
            binary = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            return binary
        except Exception as e:
            st.warning(f"Image preprocessing failed: {str(e)}")
            return image

    def detect_plate_from_url(self, image_url: str, progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Detect plate using multiple OCR methods with progress tracking"""
        try:
            # Download and prepare image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            image = Image.open(BytesIO(response.content))
            image_np = np.array(image)
            
            # Convert RGBA to RGB if needed
            if len(image_np.shape) == 3 and image_np.shape[2] == 4:
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
            
            # Preprocess image
            processed = self.preprocess_image(image_np)
            
            methods = []
            if self.pyzbar_available:
                methods.append(("pyzbar", self._try_pyzbar))
            methods.append(("tesseract", self._try_tesseract))
            if self.textract_available:
                methods.append(("textract", self._try_textract))
            if self.kraken_available:
                methods.append(("kraken", self._try_kraken))
            
            total_methods = len(methods)
            
            for idx, (method_name, method_func) in enumerate(methods):
                try:
                    if progress_bar:
                        progress = (idx + 1) / total_methods
                        progress_bar.progress(progress, f"Trying {method_name}...")
                    
                    plate = method_func(processed)
                    if plate:
                        if progress_bar:
                            progress_bar.progress(1.0, f"Found plate with {method_name}: {plate}")
                        return plate
                except Exception as e:
                    st.warning(f"{method_name} failed: {str(e)}")
                    continue
            
            if progress_bar:
                progress_bar.progress(1.0, "No plate found")
            return None
            
        except requests.RequestException as e:
            st.error(f"Failed to download image: {str(e)}")
            return None
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
            return None

    def _try_pyzbar(self, image: np.ndarray) -> Optional[str]:
        """Try detection with pyzbar"""
        if not self.pyzbar_available:
            return None
            
        try:
            from pyzbar.pyzbar import decode
            decoded = decode(image)
            for d in decoded:
                text = d.data.decode()
                plate = self.validate_plate(text)
                if plate:
                    return plate
        except Exception as e:
            st.warning(f"pyzbar detection failed: {str(e)}")
        return None

    def _try_tesseract(self, image: np.ndarray) -> Optional[str]:
        """Try detection with Tesseract"""
        try:
            text = pytesseract.image_to_string(image, config=self.tesseract_config)
            return self.validate_plate(text)
        except Exception as e:
            st.warning(f"Tesseract detection failed: {str(e)}")
            return None

    def _try_textract(self, image: np.ndarray) -> Optional[str]:
        """Try detection with textract"""
        if not self.textract_available:
            return None
            
        try:
            import textract
            import tempfile
            import os
            
            # Save temp image
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp:
                cv2.imwrite(temp.name, image)
                text = textract.process(temp.name).decode()
            
            # Clean up
            try:
                os.unlink(temp.name)
            except:
                pass
                
            return self.validate_plate(text)
        except Exception as e:
            st.warning(f"textract detection failed: {str(e)}")
            return None

    def _try_kraken(self, image: np.ndarray) -> Optional[str]:
        """Try detection with Kraken"""
        if not self.kraken_available:
            return None
            
        try:
            from kraken import pageseg
            
            # Ensure image is grayscale
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Segment and recognize
            segments = pageseg.segment(image)
            text = " ".join(segment.text for segment in segments)
            
            return self.validate_plate(text)
        except Exception as e:
            st.warning(f"Kraken detection failed: {str(e)}")
            return None

    def validate_plate(self, text: str) -> Optional[str]:
        """Validate and format potential Italian plate"""
        if not text:
            return None
            
        # Clean text
        text = text.upper().strip()
        text = re.sub(r'[^A-Z0-9]', '', text)
        
        # Plate patterns
        patterns = [
            r'[A-Z]{2}\d{3}[A-Z]{2}',  # Standard
            r'[A-Z]{2}\d{5}',          # Old format
            r'[A-Z]{2}\d{4}[A-Z]{1,2}' # Other formats
        ]
        
        # Check direct patterns
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        # Try common corrections
        corrections = {
            '0': 'O', 'O': '0',
            'I': '1', '1': 'I',
            'S': '5', '5': 'S',
            'B': '8', '8': 'B'
        }
        
        for old, new in corrections.items():
            corrected = text.replace(old, new)
            for pattern in patterns:
                match = re.search(pattern, corrected)
                if match:
                    return match.group(0)
        
        return None