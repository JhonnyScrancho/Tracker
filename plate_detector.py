import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re
import cv2
import numpy as np

class PlateDetector:
    def __init__(self):
        """Inizializza il detector di targhe"""
        self.cv2 = None
        self.tesseract_config = '--oem 3 --psm 6'
        
        # Try importing OpenCV, but continue if not available
        try:
            import cv2
            self.cv2 = cv2
        except ImportError:
            print("OpenCV not available. Image preprocessing will be disabled.")

    def preprocess_image(self, image):
        """Preprocessa l'immagine per migliorare il riconoscimento della targa"""
        if self.cv2 is None:
            return image
            
        # Converti in scala di grigi
        gray = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2GRAY)
        
        # Applica threshold adattivo
        binary = self.cv2.adaptiveThreshold(
            gray, 255, 
            self.cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            self.cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Riduzione rumore
        denoised = self.cv2.fastNlMeansDenoising(binary)
        
        return denoised

    def detect_plate_from_url(self, image_url: str) -> str:
        """Rileva la targa da un'immagine tramite URL"""
        if self.cv2 is None:
            return None
            
        try:
            # Scarica l'immagine
            response = requests.get(image_url)
            image = Image.open(BytesIO(response.content))
            
            # Converti in array numpy per OpenCV
            image_np = np.array(image)
            
            # Preprocessa l'immagine
            processed = self.preprocess_image(image_np)
            
            # Esegui OCR
            text = pytesseract.image_to_string(processed, config=self.tesseract_config)
            
            # Cerca e valida la targa
            plate = self.validate_plate(text)
            
            return plate
            
        except Exception as e:
            print(f"Errore nel processing dell'immagine: {str(e)}")
            return None

    def detect_plates_from_listing(self, image_urls: list) -> str:
        """Cerca la targa in tutte le immagini di un annuncio"""
        if self.cv2 is None or not image_urls:
            return None
            
        for url in image_urls:
            plate = self.detect_plate_from_url(url)
            if plate:
                return plate
                
        return None

    def validate_plate(self, text: str) -> str:
        """Valida e formatta una potenziale targa italiana"""
        if not text:
            return None
        
        patterns = [
            r'[A-Z]{2}\s*\d{3}\s*[A-Z]{2}',  # Format XX000XX
            r'[A-Z]{2}\s*\d{5}',              # Format XX00000
            r'[A-Z]{2}\s*\d{4}\s*[A-Z]{1,2}'  # Other common formats
        ]
        
        text = text.upper()
        text = re.sub(r'[^A-Z0-9]', '', text)
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None