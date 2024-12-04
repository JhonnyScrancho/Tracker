from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import requests
from io import BytesIO
import re
import streamlit as st
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import time

class PlateDetector:
    def __init__(self):
        """Inizializza il detector con Azure Computer Vision"""
        try:
            self.client = ComputerVisionClient(
                endpoint=st.secrets["azure"]["endpoint"],
                credentials=CognitiveServicesCredentials(st.secrets["azure"]["key"])
            )
            self.results_cache = {}
            self.debug_mode = False  # Abilita/disabilita debug
        except Exception as e:
            st.error(f"Errore inizializzazione Azure Vision: {str(e)}")
            self.client = None

    def _enhance_image(self, image_url: str, plate_area: Optional[Tuple[int, int, int, int]] = None) -> Optional[BytesIO]:
        """
        Migliora la qualità dell'immagine usando tecniche avanzate di preprocessing
        
        Args:
            image_url: URL dell'immagine
            plate_area: Opzionale, coordinate dell'area della targa (x1, y1, x2, y2)
        """
        try:
            # Download immagine
            response = requests.get(image_url, timeout=10)
            img = Image.open(BytesIO(response.content))
            
            # Se specificata, ritaglia l'area della targa
            if plate_area:
                img = img.crop(plate_area)
            
            # Converti in RGB se necessario
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Serie di miglioramenti calibrati per targhe italiane
            enhancements = [
                # 1. Bilancia il colore
                lambda x: ImageOps.autocontrast(x, cutoff=0.5),
                
                # 2. Aumenta nitidezza selettiva
                lambda x: x.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)),
                
                # 3. Regola contrasto locale
                lambda x: ImageEnhance.Contrast(x).enhance(1.8),
                
                # 4. Ottimizza luminosità
                lambda x: ImageEnhance.Brightness(x).enhance(1.2),
                
                # 5. Riduzione rumore selettiva
                lambda x: x.filter(ImageFilter.MedianFilter(size=3)),
                
                # 6. Migliora definizione bordi
                lambda x: x.filter(ImageFilter.EDGE_ENHANCE),
            ]
            
            # Applica miglioramenti in sequenza
            enhanced = img
            for enhance in enhancements:
                try:
                    enhanced = enhance(enhanced)
                except Exception as e:
                    if self.debug_mode:
                        st.warning(f"Skipping enhancement: {str(e)}")
                    continue

            # Debug: mostra immagine preprocessata
            if self.debug_mode:
                st.image([img, enhanced], caption=['Originale', 'Preprocessata'], width=300)
            
            # Converti in bytes
            img_byte_arr = BytesIO()
            enhanced.save(img_byte_arr, format='JPEG', quality=95)
            img_byte_arr.seek(0)
            
            return img_byte_arr
            
        except Exception as e:
            st.warning(f"Errore nel preprocessing: {str(e)}")
            return None

    def _validate_plate(self, text: str) -> Optional[str]:
        """
        Valida il formato targa italiana con regole migliorate
        
        Args:
            text: Testo da validare
            
        Returns:
            Targa validata o None
        """
        if not text:
            return None
            
        # Pulizia testo
        text = ''.join(c for c in text.upper() if c.isalnum())
        
        # Pattern targhe italiane
        patterns = [
            # 1. Formato standard attuale (es. FL694XB)
            r'^[ABCDEFGHJKLMNPRSTVWXYZ]{2}\d{3}[ABCDEFGHJKLMNPRSTVWXYZ]{2}$',
            
            # 2. Vecchio formato (es. MI123456)
            r'^[A-Z]{2}\d{5,6}$',
            
            # 3. Formato speciale (es. EI123AB)
            r'^[A-Z]{2}\d{4}[A-Z]$',
            
            # 4. Formato rimorchi (es. XA123YZ)
            r'^X[A-Z]\d{3}[A-Z]{2}$',
            
            # 5. Formato prova (es. P123456)
            r'^P\d{6}$'
        ]
        
        common_errors = {
            '0': 'O',
            'O': '0',
            'I': '1',
            '1': 'I',
            'S': '5',
            '5': 'S',
            'B': '8',
            '8': 'B'
        }
        
        # Prova pattern originale
        for pattern in patterns:
            if match := re.match(pattern, text):
                plate = match.group(0)
                # Verifica caratteri non validi nelle prime due posizioni
                if any(c in 'IOQU' for c in plate[:2]):
                    continue
                return plate
        
        # Prova correzioni comuni
        for old, new in common_errors.items():
            corrected_text = text.replace(old, new)
            for pattern in patterns:
                if match := re.match(pattern, corrected_text):
                    plate = match.group(0)
                    if any(c in 'IOQU' for c in plate[:2]):
                        continue
                    if self.debug_mode:
                        st.info(f"Correzione applicata: {text} -> {plate}")
                    return plate
                
        return None

    def _analyze_image(self, image: BytesIO) -> List[str]:
        """
        Analizza l'immagine con Azure Vision e restituisce tutti i testi trovati
        
        Args:
            image: Immagine in formato BytesIO
            
        Returns:
            Lista di testi trovati
        """
        try:
            result = self.client.read_in_stream(image, raw=True)
            operation_location = result.headers["Operation-Location"]
            operation_id = operation_location.split("/")[-1]

            # Polling con timeout
            timeout = time.time() + 30  # 30 secondi timeout
            while True:
                get_text_result = self.client.get_read_result(operation_id)
                if get_text_result.status not in ['notStarted', 'running']:
                    break
                if time.time() > timeout:
                    raise TimeoutError("Timeout nell'analisi dell'immagine")
                time.sleep(1)

            if get_text_result.status == OperationStatusCodes.succeeded:
                texts = []
                for text_result in get_text_result.analyze_result.read_results:
                    for line in text_result.lines:
                        texts.append(line.text)
                return texts
            return []
            
        except Exception as e:
            st.error(f"Errore nell'analisi dell'immagine: {str(e)}")
            return []

    def detect_plate_from_url(self, image_url: str, 
                            progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """
        Rileva targa usando strategia multi-step
        
        Args:
            image_url: URL dell'immagine
            progress_bar: Progress bar di Streamlit
            
        Returns:
            Targa trovata o None
        """
        try:
            # Check cache
            if image_url in self.results_cache:
                cached = self.results_cache[image_url]
                if 'plate' in cached:
                    age = (datetime.now() - cached['timestamp']).total_seconds()
                    if age < 3600:  # Cache valida per 1 ora
                        return cached['plate']
            
            if progress_bar:
                progress_bar.progress(0.2, "Preprocessando immagine...")

            # Multi-step enhancement
            plates_found = []
            confidence_scores = []
            
            # Step 1: Prova con immagine originale
            texts = self._analyze_image(BytesIO(requests.get(image_url).content))
            for text in texts:
                if plate := self._validate_plate(text):
                    plates_found.append(plate)
                    confidence_scores.append(0.6)  # Confidenza base
            
            if progress_bar:
                progress_bar.progress(0.4, "Applicando miglioramenti...")
                
            # Step 2: Prova con enhancement base
            enhanced_image = self._enhance_image(image_url)
            if enhanced_image:
                texts = self._analyze_image(enhanced_image)
                for text in texts:
                    if plate := self._validate_plate(text):
                        plates_found.append(plate)
                        confidence_scores.append(0.8)  # Confidenza maggiore
            
            if progress_bar:
                progress_bar.progress(0.6, "Analisi avanzata...")
                
            # Step 3: Prova con enhancement aggressivo
            enhanced_aggressive = self._enhance_image(image_url, plate_area=None)  # TODO: implementare detection area targa
            if enhanced_aggressive:
                texts = self._analyze_image(enhanced_aggressive)
                for text in texts:
                    if plate := self._validate_plate(text):
                        plates_found.append(plate)
                        confidence_scores.append(1.0)  # Massima confidenza
            
            if progress_bar:
                progress_bar.progress(0.8, "Validazione risultati...")
            
            # Analisi risultati
            if plates_found:
                # Seleziona la targa più frequente con confidenza più alta
                from collections import Counter
                plate_counts = Counter(plates_found)
                best_plate = max(plate_counts.items(), key=lambda x: (x[1], max(confidence_scores[i] 
                                for i, p in enumerate(plates_found) if p == x[0])))[0]
                
                # Cache result
                self.results_cache[image_url] = {
                    'plate': best_plate,
                    'timestamp': datetime.now()
                }
                
                if progress_bar:
                    progress_bar.progress(1.0, f"✅ Targa trovata: {best_plate}")
                return best_plate
            
            if progress_bar:
                progress_bar.progress(1.0, "❌ Nessuna targa trovata")
            return None
            
        except Exception as e:
            st.error(f"Errore nel rilevamento targa: {str(e)}")
            return None

    def detect_with_retry(self, image_url: str, max_retries: int = 2) -> Optional[str]:
        """
        Esegue il rilevamento con retry automatici e feedback
        
        Args:
            image_url: URL dell'immagine
            max_retries: Numero massimo di tentativi
            
        Returns:
            Targa trovata o None
        """
        for attempt in range(max_retries):
            try:
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                progress_bar.progress(0.2, f"Tentativo {attempt + 1}/{max_retries}")
                
                if plate := self.detect_plate_from_url(image_url, progress_bar):
                    progress_text.success(f"✅ Targa rilevata al tentativo {attempt + 1}")
                    return plate
                
                progress_text.warning(f"⚠️ Tentativo {attempt + 1} fallito, riprovo...")
                time.sleep(1)
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    st.error(f"❌ Tutti i tentativi falliti: {str(e)}")
                    return None
                time.sleep(1)
        
        return None

    def clear_cache(self):
        """Pulisce la cache dei risultati"""
        self.results_cache = {}

    def set_debug_mode(self, enabled: bool):
        """Imposta la modalità debug"""
        self.debug_mode = enabled