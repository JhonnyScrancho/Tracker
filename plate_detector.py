import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re
import cv2
import numpy as np
import streamlit as st
from typing import Optional
from pyzbar.pyzbar import decode
import easyocr
from pdf2image import convert_from_bytes

class PlateDetector:
    def __init__(self):
        """Initialize detector with multiple OCR engines"""
        self.tesseract_config = '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        # Initialize EasyOCR reader only once
        self.reader = easyocr.Reader(['en', 'it'])

    def detect_plate_from_url(self, image_url: str, progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Detect plate using multiple OCR methods with fallbacks"""
        try:
            # Download image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            image_bytes = response.content
            
            # Convert to PIL Image
            image = Image.open(BytesIO(image_bytes))
            image_np = np.array(image)
            
            # Convert RGBA to RGB if needed
            if len(image_np.shape) == 3 and image_np.shape[2] == 4:
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)

            # 1. Try pyzbar first (fastest)
            if progress_bar:
                progress_bar.progress(0.25, "Checking for barcodes...")
            try:
                plate = self._try_pyzbar(image_np)
                if plate:
                    return plate
            except Exception as e:
                st.warning(f"Barcode detection failed: {e}")

            # 2. Try Tesseract
            if progress_bar:
                progress_bar.progress(0.5, "Running Tesseract OCR...")
            try:
                processed = self.preprocess_image(image_np)
                plate = self._try_tesseract(processed)
                if plate:
                    return plate
            except Exception as e:
                st.warning(f"Tesseract OCR failed: {e}")

            # 3. Try EasyOCR
            if progress_bar:
                progress_bar.progress(0.75, "Running EasyOCR...")
            try:
                plate = self._try_easyocr(image_np)
                if plate:
                    return plate
            except Exception as e:
                st.warning(f"EasyOCR failed: {e}")

            # 4. If image might be a PDF, try pdf2image
            if image_url.lower().endswith('.pdf'):
                if progress_bar:
                    progress_bar.progress(0.9, "Checking PDF content...")
                try:
                    plate = self._try_pdf_ocr(image_bytes)
                    if plate:
                        return plate
                except Exception as e:
                    st.warning(f"PDF processing failed: {e}")

            if progress_bar:
                progress_bar.progress(1.0, "No plate found")
            return None

        except Exception as e:
            st.error(f"Plate detection failed: {str(e)}")
            return None

    def _try_pyzbar(self, image: np.ndarray) -> Optional[str]:
        """Try to find plate in QR codes or barcodes"""
        decoded = decode(image)
        for d in decoded:
            text = d.data.decode()
            plate = self.validate_plate(text)
            if plate:
                return plate
        return None

    def _try_tesseract(self, image: np.ndarray) -> Optional[str]:
        """Try Tesseract OCR with preprocessing"""
        text = pytesseract.image_to_string(image, config=self.tesseract_config)
        return self.validate_plate(text)

    def _try_easyocr(self, image: np.ndarray) -> Optional[str]:
        """Try EasyOCR for more robust text detection"""
        results = self.reader.readtext(image)
        for bbox, text, conf in results:
            if conf > 0.5:  # Confidence threshold
                plate = self.validate_plate(text)
                if plate:
                    return plate
        return None

    def _try_pdf_ocr(self, pdf_bytes: bytes) -> Optional[str]:
        """Extract text from PDF and try to find plate"""
        images = convert_from_bytes(pdf_bytes)
        for img in images:
            img_np = np.array(img)
            # Try all OCR methods on each page
            plate = self._try_tesseract(img_np) or \
                   self._try_easyocr(img_np) or \
                   self._try_pyzbar(img_np)
            if plate:
                return plate
        return None

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Enhanced image preprocessing"""
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Multiple preprocessing attempts
            results = []
            
            # 1. Basic preprocessing
            basic = self._basic_preprocessing(gray)
            results.append(basic)
            
            # 2. High contrast
            contrast = self._high_contrast_preprocessing(gray)
            results.append(contrast)
            
            # 3. Denoised
            denoised = self._denoised_preprocessing(gray)
            results.append(denoised)
            
            # Try OCR on each version and return first success
            for processed in results:
                text = pytesseract.image_to_string(processed, config=self.tesseract_config)
                if self.validate_plate(text):
                    return processed
            
            # If no version yields a plate, return the basic preprocessing
            return basic
            
        except Exception as e:
            st.warning(f"Preprocessing failed: {str(e)}")
            return image

    def _basic_preprocessing(self, gray: np.ndarray) -> np.ndarray:
        """Basic image preprocessing"""
        resized = cv2.resize(gray, None, fx=2.0, fy=2.0)
        blurred = cv2.GaussianBlur(resized, (5, 5), 0)
        return cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    def _high_contrast_preprocessing(self, gray: np.ndarray) -> np.ndarray:
        """High contrast preprocessing"""
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        return cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

    def _denoised_preprocessing(self, gray: np.ndarray) -> np.ndarray:
        """Denoised preprocessing"""
        denoised = cv2.fastNlMeansDenoising(gray)
        return cv2.threshold(denoised, 127, 255, cv2.THRESH_BINARY)[1]

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
        
        # Direct pattern match
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        # Common OCR corrections
        corrections = {
            '0': 'O', 'O': '0',
            'I': '1', '1': 'I',
            'S': '5', '5': 'S',
            'B': '8', '8': 'B',
            'Z': '2', '2': 'Z'
        }
        
        # Try each correction
        for old, new in corrections.items():
            corrected = text.replace(old, new)
            for pattern in patterns:
                match = re.search(pattern, corrected)
                if match:
                    return match.group(0)
        
        return None