import argparse
import logging
import signal
import threading
import time
from nfc.reader import NFCReader


def list_readers():
    try:
        from smartcard.System import readers
    except ImportError as exc:
        raise RuntimeError('Telepítsd a pyscard csomagot és a PC/SC drivert.') from exc
    return readers()

def print_reader_report():
    available=list_readers()
    if not available:
        print('Nem található NFC/PC/SC olvasó.')
        print('Ellenőrizd az USB-kapcsolatot, a gyártói drivert és a Windows Smart Card szolgáltatást.')
        return 1
    for index,reader in enumerate(available,1):
        print(f'{index}. {reader}')
        try:
            connection=reader.createConnection()
            connection.connect()
            print('   Állapot: kártya jelen van')
            connection.disconnect()
        except Exception as exc:
            print(f'   Állapot: olvasó elérhető, kártya nincs behelyezve ({exc})')
    return 0

def scan_loop():
    reader=NFCReader()
    stopped=threading.Event()
    def stop(_signal,_frame):
        stopped.set()
        reader.stop()
    signal.signal(signal.SIGINT,stop)
    if hasattr(signal,'SIGTERM'):
        signal.signal(signal.SIGTERM,stop)
    last_card=[None]
    def on_card(card_id):
        last_card[0]=card_id
        print(f'UID: {card_id}')
    def on_error(error):
        logging.warning('Olvasó újracsatlakozása szükséges: %s',error)
    print('Tarts egy kártyát az olvasóhoz. Kilépéshez Ctrl+C.')
    try:
        reader.start(on_card,on_error)
    except KeyboardInterrupt:
        stop(None,None)
    return 0

def main():
    parser=argparse.ArgumentParser(description='PC/SC olvasó diagnosztika és UID-próba')
    parser.add_argument('--scan',action='store_true',help='Folyamatos UID-olvasási mód')
    parser.add_argument('--verbose',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    try:
        return scan_loop() if args.scan else print_reader_report()
    except (RuntimeError,ImportError) as exc:
        parser.exit(1,f'Hiba: {exc}\n')

if __name__=='__main__':
    raise SystemExit(main())
