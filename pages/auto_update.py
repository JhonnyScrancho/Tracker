import streamlit as st
from datetime import datetime
from services.tracker import AutoTracker

st.set_page_config(page_title="Auto Update", page_icon="🔄")

def main():
    tracker = AutoTracker()
    
    # Recupera configurazione scheduler
    config = tracker.get_scheduler_config()
    
    if not config or not config.get('enabled'):
        st.info("Aggiornamento automatico disabilitato")
        return
        
    now = datetime.now()
    scheduled_time = now.replace(
        hour=config.get('hour', 1),
        minute=config.get('minute', 0)
    )
    
    # Se è l'ora di eseguire l'aggiornamento
    if now.hour == scheduled_time.hour and now.minute >= scheduled_time.minute:
        st.write("🔄 Avvio aggiornamento automatico...")
        
        # Recupera dealer attivi
        dealers = tracker.get_dealers()
        for dealer in dealers:
            try:
                st.write(f"📥 Aggiornamento {dealer['url']}...")
                listings = tracker.scrape_dealer(dealer['url'])
                
                if listings:
                    tracker.save_listings(listings)
                    tracker.mark_inactive_listings(
                        dealer['id'], 
                        [l['id'] for l in listings]
                    )
                    st.success(f"✅ Aggiornati {len(listings)} annunci")
                    
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")
                continue
                
        # Aggiorna timestamp
        tracker.save_scheduler_config({
            'last_update': now
        })
        st.success("✅ Aggiornamento completato!")
    else:
        st.info(f"⏰ Prossimo aggiornamento programmato per le {scheduled_time.strftime('%H:%M')}")

if __name__ == "__main__":
    main()