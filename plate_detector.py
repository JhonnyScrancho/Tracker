import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re
import cv2
import numpy as np

class PlateDetector:
    def __init__(self):
        """Inizializza il detector di targhe con solo Tesseract"""
        self.cv2 = None
        self.tesseract_config = '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        
        try:
            import cv2
            self.cv2 = cv2
        except ImportError:
            print("OpenCV not available. Image preprocessing will be disabled.")

    def preprocess_image(self, image):
        """Preprocessa l'immagine per migliorare il riconoscimento della targa"""
        if self.cv2 is None:
            return image
            
        try:
            # Converti in scala di grigi
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Aumenta il contrasto
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)
            
            # Riduzione rumore
            denoised = cv2.fastNlMeansDenoising(gray)
            
            # Thresholding adattivo
            binary = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            return binary
            
        except Exception as e:
            print(f"Errore nel preprocessing: {str(e)}")
            return image

    def detect_plate_from_url(self, image_url: str) -> str:
        """Rileva la targa usando solo Tesseract"""
        try:
            # Scarica l'immagine
            response = requests.get(image_url)
            image = Image.open(BytesIO(response.content))
            image_np = np.array(image)
            
            # Se l'immagine è in formato RGBA, converti in RGB
            if len(image_np.shape) == 3 and image_np.shape[2] == 4:
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
            
            # Preprocessa l'immagine
            processed = self.preprocess_image(image_np)
            
            # Esegui OCR
            text = pytesseract.image_to_string(processed, config=self.tesseract_config)
            return self.validate_plate(text)
            
        except Exception as e:
            print(f"Errore nel processing dell'immagine: {str(e)}")
            return None

    def validate_plate(self, text: str) -> str:
        """Valida e formatta una potenziale targa italiana"""
        if not text:
            return None
            
        # Pulizia e normalizzazione
        text = text.upper().strip()
        text = re.sub(r'[^A-Z0-9]', '', text)
        
        # Pattern targhe italiane
        patterns = [
            r'[A-Z]{2}\d{3}[A-Z]{2}',  # Standard (es. FT831AG)
            r'[A-Z]{2}\d{5}',          # Vecchio formato
            r'[A-Z]{2}\d{4}[A-Z]{1,2}' # Altri formati validi
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        # Prova correzioni comuni
        corrections = {
            '0': 'O',
            'O': '0',
            'I': '1',
            '1': 'I',
            'S': '5',
            '5': 'S'
        }
        
        for old, new in corrections.items():
            corrected_text = text.replace(old, new)
            for pattern in patterns:
                match = re.search(pattern, corrected_text)
                if match:
                    return match.group(0)
        
        return None

    def detect_plates_from_listing(self, image_urls: list) -> str:
        """Cerca la targa in tutte le immagini di un annuncio"""
        if not image_urls:
            return None
            
        for url in image_urls:
            try:
                plate = self.detect_plate_from_url(url)
                if plate:
                    return plate
            except Exception as e:
                print(f"Errore nell'analisi dell'immagine {url}: {str(e)}")
                continue
                
        return None