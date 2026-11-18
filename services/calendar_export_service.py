from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

class CalendarExportService:
    @staticmethod
    def _escape(value):
        text=str(value or '')
        return text.replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\r','').replace('\n','\\n')

    @staticmethod
    def _utc(value):
        if value.tzinfo is None:
            value=value.replace(tzinfo=ZoneInfo('Europe/Budapest'))
        return value.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

    def render(self,events,*,calendar_name='Egyetemi kurzusalkalmak'):
        lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//NFC Attendance//HU',
               'CALSCALE:GREGORIAN','METHOD:PUBLISH',
               'X-WR-CALNAME:'+self._escape(calendar_name)]
        stamp=self._utc(datetime.now(ZoneInfo('Europe/Budapest')))
        for event in events:
            summary=' · '.join(filter(None,[event.get('code'),event.get('title') or event.get('name')]))
            description=event.get('name') or event.get('course_name') or ''
            location=event.get('room') or ''
            lines.extend(['BEGIN:VEVENT',
                'UID:'+str(event.get('id') or uuid4())+'@attendance.local',
                'DTSTAMP:'+stamp,
                'DTSTART:'+self._utc(event['starts_at']),
                'DTEND:'+self._utc(event['ends_at']),
                'SUMMARY:'+self._escape(summary),
                'DESCRIPTION:'+self._escape(description),
                'LOCATION:'+self._escape(location),
                'STATUS:'+('CANCELLED' if event.get('status')=='cancelled' else 'CONFIRMED'),
                'END:VEVENT'])
        lines.append('END:VCALENDAR')
        return '\r\n'.join(lines)+'\r\n'
