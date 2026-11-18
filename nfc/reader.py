import logging
import threading

try:
    from smartcard.System import readers
    from smartcard.util import toHexString
    from smartcard.CardRequest import CardRequest
    from smartcard.Exceptions import CardRequestTimeoutException
except ImportError:
    readers = None
    toHexString = None
    CardRequest = None
    CardRequestTimeoutException = None

log = logging.getLogger(__name__)

class NFCReader:
    def __init__(self, poll_interval=0.35, reconnect_interval=2.0):
        self.reader = None
        self._last_reader_name = None
        self.running = threading.Event()
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._stopped = False
        self.poll_interval = poll_interval
        self.reconnect_interval = reconnect_interval

    def connect(self):
        if readers is None:
            raise RuntimeError('A pyscard csomag nincs telepítve.')
        available = readers()
        if not available:
            raise RuntimeError('Nem található PC/SC NFC-olvasó.')
        self.reader = available[0]
        reader_name = str(self.reader)
        if reader_name != self._last_reader_name:
            log.info('NFC-olvasó csatlakoztatva: %s', reader_name)
            self._last_reader_name = reader_name
        return self.reader

    def read_uid(self, connection):
        for command in ([0xFF, 0xCA, 0x00, 0x00, 0x00], [0xFF, 0xCA, 0x01, 0x00, 0x00]):
            try:
                data, sw1, sw2 = connection.transmit(command)
                if sw1 == 0x90 and data:
                    return toHexString(data).replace(' ', '').upper()
            except Exception as exc:
                log.debug('UID lekérdezés sikertelen: %s', exc)
        return None

    @staticmethod
    def _is_card_state_error(error):
        message = str(error).casefold()
        return any(value in message for value in ('0x80100069', '0x80100066', 'card was removed', 'card has been removed', 'kártya el lett távolítva', 'nem válaszol az alaphelyzetbe állítási parancsra'))

    @staticmethod
    def _is_card_removed_error(error):
        message = str(error).casefold()
        return any(value in message for value in ('0x80100069', 'card was removed', 'card has been removed', 'kártya el lett távolítva'))

    def stop(self):
        with self._state_lock:
            self._stopped = True
            self.running.clear()
            self._stop_event.set()

    def start(self, callback, on_error=None, on_ready=None):
        with self._state_lock:
            if self._stopped:
                return
            self.running.set()
        last_error = None
        ready_reported = False
        request = None
        while self.running.is_set() and not self._stop_event.is_set():
            connection = None
            try:
                if readers is None or CardRequest is None:
                    raise RuntimeError('A pyscard csomag nincs telepítve.')
                available = readers()
                if not available:
                    self.reader = None
                    ready_reported = False
                    exc = RuntimeError('Nem található PC/SC NFC-olvasó.')
                    if str(exc) != last_error:
                        log.warning('%s', exc)
                        if on_error:
                            on_error(exc)
                        last_error = str(exc)
                    self._stop_event.wait(self.reconnect_interval)
                    continue
                self.reader = available[0]
                reader_name = str(self.reader)
                if reader_name != self._last_reader_name:
                    log.info('NFC-olvasó csatlakoztatva: %s', reader_name)
                    self._last_reader_name = reader_name
                if not ready_reported:
                    if on_ready:
                        on_ready()
                    ready_reported = True
                    last_error = None
                if request is None:
                    request = CardRequest(newcardonly=True, timeout=1)
                try:
                    card_service = request.waitforcard()
                except CardRequestTimeoutException:
                    continue
                connection = card_service.connection
                connection.connect()
                card_id = self.read_uid(connection)
                if card_id:
                    callback(card_id)
                last_error = None
            except Exception as exc:
                if str(exc) != last_error:
                    log.warning('NFC olvasási hiba: %s', exc)
                    if on_error:
                        on_error(exc)
                    last_error = str(exc)
                if '0x80100009' in str(exc):
                    self.reader = None
                    ready_reported = False
                self._stop_event.wait(self.reconnect_interval)
            finally:
                if connection is not None:
                    try:
                        connection.disconnect()
                    except Exception:
                        pass
        if request is not None:
            try:
                request.pcsccardrequest.release()
            except Exception:
                pass
