from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import firestore
from services.tracker import AutoTracker
import time

class SchedulerService:
    def __init__(self):
        """Inizializza il servizio scheduler"""
        self.db = firestore.client()
        self.tracker = AutoTracker()

    def check_and_run_scheduled_tasks(self):
        """
        Verifica e esegue i task schedulati
        Ritorna: (bool, str) - (successo, messaggio)
        """
        try:
            # Recupera configurazione scheduler
            config = self.tracker.get_scheduler_config()
            
            if not config or not config.get('enabled'):
                return False, "Scheduler non abilitato"

            now = datetime.now()
            last_update = config.get('last_update')
            
            # Se non c'è stato un aggiornamento oggi
            if not last_update or last_update.date() < now.date():
                scheduled_time = now.replace(
                    hour=config.get('hour', 1),
                    minute=config.get('minute', 0)
                )

                # Se è l'ora di eseguire l'aggiornamento
                if now >= scheduled_time:
                    # Recupera tutti i dealer attivi
                    dealers = self.tracker.get_dealers()
                    
                    for dealer in dealers:
                        try:
                            # Esegue lo scrape
                            listings = self.tracker.scrape_dealer(dealer['url'])
                            
                            if listings:
                                # Salva i nuovi annunci
                                self.tracker.save_listings(listings)
                                
                                # Marca come inattivi gli annunci non più presenti
                                self.tracker.mark_inactive_listings(
                                    dealer['id'], 
                                    [l['id'] for l in listings]
                                )
                                
                        except Exception as e:
                            print(f"Errore scrape dealer {dealer['id']}: {str(e)}")
                            continue

                    # Aggiorna timestamp ultimo aggiornamento
                    self.db.collection('config').document('scheduler').update({
                        'last_update': now
                    })
                    
                    return True, f"Aggiornamento completato per {len(dealers)} dealer"
                    
                return False, f"Prossimo aggiornamento schedulato per le {scheduled_time.strftime('%H:%M')}"
                
            return False, f"Aggiornamento già eseguito oggi alle {last_update.strftime('%H:%M')}"
            
        except Exception as e:
            return False, f"Errore durante l'esecuzione scheduler: {str(e)}"