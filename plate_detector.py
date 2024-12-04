import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re
import numpy as np
import streamlit as st
from typing import Optional
from pyzbar.pyzbar import decode

class PlateDetector:
    def __init__(self):
        """Initialize lightweight detector"""
        self.tesseract_config = '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

    def detect_plate_from_url(self, image_url: str, progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Detect plate using memory-efficient methods"""
        try:
            # Download image with timeout
            response = requests.get(image_url, timeout=5)
            response.raise_for_status()
            
            # Convert to PIL Image
            image = Image.open(BytesIO(response.content))
            image_np = np.array(image)

            # 1. Try pyzbar first (fastest)
            if progress_bar:
                progress_bar.progress(0.33, "Checking for barcodes...")
            try:
                plate = self._try_pyzbar(image)
                if plate:
                    if progress_bar:
                        progress_bar.progress(1.0, f"Found plate in barcode: {plate}")
                    return plate
            except Exception as e:
                st.warning(f"Barcode detection failed: {e}")

            # 2. Try Tesseract with basic preprocessing
            if progress_bar:
                progress_bar.progress(0.66, "Running OCR...")
            try:
                # Convert to grayscale
                image = image.convert('L')
                # Increase contrast
                image = Image.fromarray(np.uint8(np.clip((np.array(image) * 1.5), 0, 255)))
                # Run OCR
                text = pytesseract.image_to_string(image, config=self.tesseract_config)
                plate = self.validate_plate(text)
                if plate:
                    if progress_bar:
                        progress_bar.progress(1.0, f"Found plate with OCR: {plate}")
                    return plate
            except Exception as e:
                st.warning(f"OCR failed: {e}")

            if progress_bar:
                progress_bar.progress(1.0, "No plate found")
            return None

        except Exception as e:
            st.error(f"Plate detection failed: {str(e)}")
            return None

    def _try_pyzbar(self, image: Image.Image) -> Optional[str]:
        """Try to find plate in QR codes or barcodes"""
        decoded = decode(image)
        for d in decoded:
            text = d.data.decode()
            plate = self.validate_plate(text)
            if plate:
                return plate
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