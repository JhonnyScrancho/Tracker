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

    def detect_plate_from_url(self, image_url: str) -> str:
        """Rileva la targa da un'immagine tramite URL con debug avanzato"""
        if self.cv2 is None:
            return None
            
        try:
            print(f"Analisi immagine: {image_url}")
            
            # Scarica l'immagine
            response = requests.get(image_url)
            image = Image.open(BytesIO(response.content))
            
            # Converti in array numpy per OpenCV
            image_np = np.array(image)
            
            # Se l'immagine è in formato RGBA, converti in RGB
            if image_np.shape[-1] == 4:
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
                print("Convertita immagine da RGBA a RGB")
            
            # Debug dimensioni immagine
            print(f"Dimensioni immagine: {image_np.shape}")
            
            # Estrai regione di interesse (ROI) - focus sulla parte inferiore dove di solito è la targa
            height = image_np.shape[0]
            width = image_np.shape[1]
            roi_height = height // 3  # Prendi il terzo inferiore dell'immagine
            roi = image_np[height-roi_height:height, :]
            print(f"Estratta ROI: {roi.shape}")
            
            # Preprocessa l'immagine originale
            processed = self.preprocess_image(image_np)
            
            # Preprocessa la ROI
            processed_roi = self.preprocess_image(roi)
            
            # Lista di configurazioni OCR da provare
            configs = [
                '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            ]
            
            for idx, config in enumerate(configs):
                print(f"\nTentativo OCR #{idx+1} con config: {config}")
                
                # Prova OCR su immagine intera preprocessata
                text1 = pytesseract.image_to_string(processed, config=config)
                print(f"OCR immagine intera: '{text1.strip()}'")
                plate1 = self.validate_plate(text1)
                if plate1:
                    print(f"✅ Targa valida trovata nell'immagine intera: {plate1}")
                    return plate1
                
                # Prova OCR su ROI preprocessata
                text2 = pytesseract.image_to_string(processed_roi, config=config)
                print(f"OCR ROI: '{text2.strip()}'")
                plate2 = self.validate_plate(text2)
                if plate2:
                    print(f"✅ Targa valida trovata nella ROI: {plate2}")
                    return plate2
                
                # Prova OCR su immagine originale
                text3 = pytesseract.image_to_string(image_np, config=config)
                print(f"OCR immagine originale: '{text3.strip()}'")
                plate3 = self.validate_plate(text3)
                if plate3:
                    print(f"✅ Targa valida trovata nell'immagine originale: {plate3}")
                    return plate3

            print("❌ Nessuna targa valida trovata")
            return None
                
        except Exception as e:
            print(f"Errore nel processing dell'immagine: {str(e)}")
            return None

    def preprocess_image(self, image):
        """Preprocessa l'immagine per migliorare il riconoscimento della targa"""
        if self.cv2 is None:
            return image
            
        try:
            print("Inizio preprocessing immagine...")
            
            # Converti in scala di grigi
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            print("Convertito in scala di grigi")
            
            # Aumenta il contrasto
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)
            print("Applicato CLAHE per aumento contrasto")
            
            # Riduzione rumore
            denoised = cv2.fastNlMeansDenoising(gray)
            print("Applicata riduzione rumore")
            
            # Thresholding adattivo
            binary = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            print("Applicato thresholding adattivo")
            
            # Operazioni morfologiche per migliorare il testo
            kernel = np.ones((2,2), np.uint8)
            morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            print("Applicate operazioni morfologiche")
            
            return morph
            
        except Exception as e:
            print(f"Errore nel preprocessing: {str(e)}")
            return image

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