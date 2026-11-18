import argparse
import logging
import signal
import threading
from nfc.reader import NFCReader
from services.session_service import SessionService

log=logging.getLogger('session-reader')
stop_event=threading.Event()

def describe(result):
    status=result.get('status','ERROR')
    name=result.get('name') or result.get('card_id') or ''
    messages={
        'PRESENT':'jelenlét rögzítve','LATE':'késés rögzítve',
        'ALREADY_MARKED':'már rögzítve','UNKNOWN_CARD':'ismeretlen kártya',
        'NOT_ENROLLED':'nincs felvéve a kurzusra','SESSION_CLOSED':'az alkalom nem aktív',
        'TOO_EARLY':'még nem kezdődött el','TOO_LATE':'az időablak lejárt',
        'SESSION_NOT_FOUND':'az alkalom nem található','INVALID_CARD':'hibás UID',
    }
    print(f'{name}: {messages.get(status,status)}')

def main():
    parser=argparse.ArgumentParser(description='NFC-beolvasás egy megnyitott kurzusalkalomhoz')
    parser.add_argument('session_id',type=int)
    parser.add_argument('--log-level',default='INFO')
    args=parser.parse_args()
    logging.basicConfig(level=getattr(logging,args.log_level.upper(),logging.INFO),
                        format='%(asctime)s %(levelname)s %(message)s')
    service=SessionService();reader=NFCReader()
    session=service.get_session(args.session_id)
    if not session:
        parser.error('A megadott kurzusalkalom nem található.')
    if session['status']!='open':
        parser.error('Előbb nyisd meg a kurzusalkalmat a webes felületen.')
    print(f"Olvasás: {session['course_name']} · {session['starts_at']} · {session['room'] or 'terem nincs megadva'}")
    print('Leállítás: Ctrl+C')
    def stop(_signal,_frame):
        stop_event.set();reader.stop()
    signal.signal(signal.SIGINT,stop)
    if hasattr(signal,'SIGTERM'):
        signal.signal(signal.SIGTERM,stop)
    def on_card(card_id):
        try:
            describe(service.record_nfc(args.session_id,card_id))
        except Exception:
            log.exception('A jelenléti bejegyzést nem sikerült menteni.')
    def on_error(error):
        log.warning('NFC-olvasó hiba: %s',error)
    try:
        reader.start(on_card,on_error)
    except KeyboardInterrupt:
        stop_event.set();reader.stop()
    return 0

if __name__=='__main__':
    raise SystemExit(main())
