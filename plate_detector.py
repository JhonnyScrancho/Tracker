import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re
import cv2
import numpy as np
try:
    from pyzbar.pyzbar import decode  # Per codici QR/barcodes
    import textract  # OCR alternativo leggero
    from kraken import pageseg  # OCR specializzato per testo
except ImportError:
    print("Librerie OCR opzionali non disponibili")

class PlateDetector:
    def __init__(self):
        """Inizializza il detector con multiple librerie OCR leggere"""
        self.cv2 = None
        self.tesseract_config = '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        
        # Verifica disponibilità librerie
        try:
            import cv2
            self.cv2 = cv2
        except ImportError:
            print("OpenCV not available")
            
        try:
            import pyzbar
            self.has_pyzbar = True
        except ImportError:
            self.has_pyzbar = False
            
        try:
            import textract
            self.has_textract = True
        except ImportError:
            self.has_textract = False
            
        try:
            import kraken
            self.has_kraken = True
        except ImportError:
            self.has_kraken = False

    def preprocess_image(self, image):
        """Preprocessa l'immagine per migliorare il riconoscimento"""
        if self.cv2 is None:
            return image
            
        try:
            # Conversione scala di grigi
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Ridimensiona se l'immagine è troppo grande
            height, width = gray.shape
            if width > 1000:
                scale = 1000 / width
                gray = cv2.resize(gray, None, fx=scale, fy=scale)
            
            # Migliora contrasto
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Denoising
            denoised = cv2.fastNlMeansDenoising(enhanced)
            
            # Binarizzazione adattiva
            binary = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            return binary
        except Exception as e:
            print(f"Errore preprocessing: {str(e)}")
            return image

    def _try_pyzbar(self, image):
        """Tenta riconoscimento con pyzbar (per QR code o barcodes)"""
        if not self.has_pyzbar:
            return None
            
        try:
            decoded = decode(image)
            for d in decoded:
                text = d.data.decode()
                plate = self.validate_plate(text)
                if plate:
                    return plate
            return None
        except:
            return None

    def _try_textract(self, image_path):
        """Tenta riconoscimento con textract"""
        if not self.has_textract:
            return None
            
        try:
            # Salva temporaneamente l'immagine
            temp_path = "temp_plate.png"
            cv2.imwrite(temp_path, image)
            
            # Estrai testo
            text = textract.process(temp_path).decode()
            return self.validate_plate(text)
        except:
            return None
        finally:
            try:
                import os
                os.remove(temp_path)
            except:
                pass

    def _try_kraken(self, image):
        """Tenta riconoscimento con Kraken"""
        if not self.has_kraken:
            return None
            
        try:
            # Kraken richiede immagini binarie
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Segmentazione e riconoscimento
            segments = pageseg.segment(image)
            text = ""
            for segment in segments:
                text += segment.text + " "
            
            return self.validate_plate(text)
        except:
            return None

    def detect_plate_from_url(self, image_url: str) -> str:
        """Rileva la targa provando diversi metodi OCR in cascata"""
        try:
            # Scarica e prepara l'immagine
            response = requests.get(image_url)
            image = Image.open(BytesIO(response.content))
            image_np = np.array(image)
            
            # Converti RGBA in RGB se necessario
            if len(image_np.shape) == 3 and image_np.shape[2] == 4:
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
            
            # Preprocessa l'immagine
            processed = self.preprocess_image(image_np)
            
            # 1. Prova con pyzbar (per eventuali QR code)
            plate = self._try_pyzbar(image_np)
            if plate:
                print(f"Targa trovata con pyzbar: {plate}")
                return plate
            
            # 2. Prova con Tesseract
            text = pytesseract.image_to_string(processed, config=self.tesseract_config)
            plate = self.validate_plate(text)
            if plate:
                print(f"Targa trovata con Tesseract: {plate}")
                return plate
            
            # 3. Prova con textract
            plate = self._try_textract(processed)
            if plate:
                print(f"Targa trovata con textract: {plate}")
                return plate
            
            # 4. Ultimo tentativo con Kraken
            plate = self._try_kraken(processed)
            if plate:
                print(f"Targa trovata con Kraken: {plate}")
                return plate
            
            return None
            
        except Exception as e:
            print(f"Errore nel processing dell'immagine: {str(e)}")
            return None

    def validate_plate(self, text: str) -> str:
        """Valida e formatta una potenziale targa italiana"""
        if not text:
            return None
            
        # Pulizia testo
        text = text.upper().strip()
        text = re.sub(r'[^A-Z0-9]', '', text)
        
        # Pattern targhe
        patterns = [
            r'[A-Z]{2}\d{3}[A-Z]{2}',  # Standard
            r'[A-Z]{2}\d{5}',          # Vecchio formato
            r'[A-Z]{2}\d{4}[A-Z]{1,2}' # Altri formati
        ]
        
        # Controlla pattern diretti
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        # Prova correzioni comuni
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