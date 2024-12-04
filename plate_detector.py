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
        # Configurazione tesseract ottimizzata per targhe
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
            
        # Converte in scala di grigi
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Aumenta il contrasto con equalizzazione dell'istogramma
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        
        # Riduzione rumore
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Sogliatura adattiva
        binary = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Operazioni morfologiche per pulire il testo
        kernel = np.ones((2,2), np.uint8)
        morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return morph

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
            
            # Se l'immagine è in formato RGBA, converti in RGB
            if image_np.shape[-1] == 4:
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
            
            # Preprocessa l'immagine
            processed = self.preprocess_image(image_np)
            
            # Esegui OCR multiplo con diverse configurazioni
            # Prima prova con l'immagine preprocessata
            text1 = pytesseract.image_to_string(processed, config=self.tesseract_config)
            plate1 = self.validate_plate(text1)
            if plate1:
                return plate1
                
            # Se non trova, prova con l'immagine originale in scala di grigi
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
            text2 = pytesseract.image_to_string(gray, config=self.tesseract_config)
            plate2 = self.validate_plate(text2)
            if plate2:
                return plate2
                
            # Ultima prova con l'immagine originale
            text3 = pytesseract.image_to_string(image_np, config=self.tesseract_config)
            plate3 = self.validate_plate(text3)
            return plate3
            
        except Exception as e:
            print(f"Errore nel processing dell'immagine: {str(e)}")
            return None

    def validate_plate(self, text: str) -> str:
        """Valida e formatta una potenziale targa italiana"""
        if not text:
            return None
            
        # Pulizia del testo
        text = text.upper().strip()
        text = re.sub(r'[^A-Z0-9]', '', text)
        
        # Pattern per targhe italiane
        patterns = [
            r'^[A-Z]{2}\d{3}[A-Z]{2}$',     # Standard (FT831AG)
            r'^[A-Z]{2}\d{5}$',              # Vecchio formato
            r'^[A-Z]{2}\d{4}[A-Z]{1,2}$'     # Altri formati validi
        ]
        
        # Prima verifica pattern esatti
        for pattern in patterns:
            if re.match(pattern, text):
                return text
        
        # Se non trova match esatti, cerca pattern più flessibili
        text = re.sub(r'[^A-Z0-9]', '', text)
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
                
        # Ultimo tentativo con correzioni comuni
        text = text.replace('0', 'O').replace('1', 'I').replace('5', 'S')
        for pattern in patterns:
            if re.match(pattern, text):
                return text
                
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