"""Real message artifacts for the communication tools.

The email and calendar tools previously wrote a JSON stub, which is not usable
by anything. These build genuine files instead:

- `.eml` (RFC 5322) opens in any mail client and can be forwarded or archived.
- `.ics` (RFC 5545) imports into any calendar.

Neither requires network access, so both work in an air-gapped deployment.
Actual SMTP delivery is separate and opt-in: `send_smtp` is only called when an
SMTP host is configured, and the policy engine already routes `send_email`
through human approval.
"""
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


def _recipients(value):
    if not value:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(';', ',').split(',') if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


def build_email(args):
    """Build an RFC 5322 message from tool arguments."""
    message = EmailMessage()
    message['To'] = ', '.join(_recipients(args.get('to'))) or 'undisclosed-recipients:;'
    if args.get('cc'):
        message['Cc'] = ', '.join(_recipients(args.get('cc')))
    message['From'] = args.get('from') or 'sovereign-agent@localhost'
    message['Subject'] = args.get('subject') or '(no subject)'
    message['Date'] = formatdate(localtime=True)
    message['Message-ID'] = make_msgid(domain='sovereign-agent.local')
    # Mark machine-generated mail so recipients and filters can tell.
    message['X-Generated-By'] = 'Sovereign Agent Orchestrator'
    message.set_content(args.get('body') or args.get('content') or '')
    return message


def _ics_escape(value):
    return (str(value or '')
            .replace('\\', '\\\\').replace(';', r'\;')
            .replace(',', r'\,').replace('\n', r'\n'))


def _ics_time(value):
    """Accept ISO-8601 or datetime; fall back to 'now' for unparseable input."""
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            moment = datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def build_ics(args):
    """Build an RFC 5545 VEVENT."""
    start_raw = args.get('start') or args.get('start_time') or datetime.now(timezone.utc)
    start = _ics_time(start_raw)
    if args.get('end') or args.get('end_time'):
        end = _ics_time(args.get('end') or args.get('end_time'))
    else:
        try:
            base = datetime.strptime(start, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        except ValueError:
            base = datetime.now(timezone.utc)
        minutes = int(args.get('duration_minutes') or 60)
        end = _ics_time(base + timedelta(minutes=minutes))

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Sovereign Agent Orchestrator//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{uuid.uuid4()}@sovereign-agent.local',
        f'DTSTAMP:{_ics_time(datetime.now(timezone.utc))}',
        f'DTSTART:{start}',
        f'DTEND:{end}',
        f'SUMMARY:{_ics_escape(args.get("title") or args.get("summary") or "Untitled event")}',
    ]
    if args.get('description') or args.get('body'):
        lines.append(f'DESCRIPTION:{_ics_escape(args.get("description") or args.get("body"))}')
    if args.get('location'):
        lines.append(f'LOCATION:{_ics_escape(args.get("location"))}')
    for attendee in _recipients(args.get('attendees')):
        lines.append(f'ATTENDEE;RSVP=TRUE:mailto:{attendee}')
    lines += ['END:VEVENT', 'END:VCALENDAR']
    # RFC 5545 requires CRLF line endings.
    return '\r\n'.join(lines) + '\r\n'


def send_smtp(message, config):
    """Deliver a built message. Only reached when an SMTP host is configured."""
    host = config.get('host')
    if not host:
        raise ValueError('SMTP_NOT_CONFIGURED')
    port = int(config.get('port') or 587)
    if config.get('from'):
        message.replace_header('From', config['from']) if 'From' in message else message.add_header('From', config['from'])
    with smtplib.SMTP(host, port, timeout=int(config.get('timeout') or 30)) as server:
        if config.get('use_tls', True):
            server.starttls()
        if config.get('user'):
            server.login(config['user'], config.get('password') or '')
        server.send_message(message)
