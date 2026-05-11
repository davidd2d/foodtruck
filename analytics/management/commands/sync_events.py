"""
Management command to synchronize analytics.Event table.

Modes:
- openagenda : fetch events from OpenAgenda API (requires OPENAGENDA_API_KEY +
               OPENAGENDA_AGENDA_UIDS env vars, or CLI args)
- fetch      : fetch events from a custom JSON URL
- seed       : generate synthetic events around active food trucks (dev/fallback)
- auto       : openagenda if key present, else fetch if URL present, else seed

Required env vars for OpenAgenda mode:
  OPENAGENDA_API_KEY      - public API key (read-only is enough)
    OPENAGENDA_AGENDA_UIDS  - optional comma-separated agenda UIDs to pull from

Optional env vars:
  ANALYTICS_EVENTS_SOURCE_URL - custom JSON feed URL (used in fetch mode)
"""

import json
import math
import os
import random
import ssl
from datetime import timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from analytics.models import Event, OpenAgendaSource
from foodtrucks.models import FoodTruck


def _to_decimal(value):
    return Decimal(str(value)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)


def _get_env(name, default=''):
    return os.getenv(name) or getattr(settings, name, '') or default


def _safe_urlopen(request, timeout=20):
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return urlopen(request, timeout=timeout, context=ssl_context)


class Command(BaseCommand):
    help = (
        'Synchronize analytics events from OpenAgenda, a custom JSON URL, or synthetic seed data. '
        'Run periodically in production (e.g. every 2 hours via cron).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            choices=['auto', 'openagenda', 'fetch', 'seed'],
            default='auto',
            help=(
                'auto=openagenda if key present, else fetch if URL set, else seed; '
                'openagenda=OpenAgenda API; fetch=custom JSON URL; seed=synthetic events.'
            ),
        )
        parser.add_argument(
            '--api-key',
            default='',
            help='OpenAgenda public API key (overrides OPENAGENDA_API_KEY env var).',
        )
        parser.add_argument(
            '--agenda-uids',
            default='',
            help='Comma-separated OpenAgenda agenda UIDs (overrides DB table and OPENAGENDA_AGENDA_UIDS env var).',
        )
        parser.add_argument(
            '--source-url',
            default='',
            help='HTTP/HTTPS URL returning a JSON array of events (fetch mode).',
        )
        parser.add_argument(
            '--horizon-days',
            type=int,
            default=60,
            help='Fetch only events starting within this many days from today.',
        )
        parser.add_argument(
            '--geo-radius-km',
            type=float,
            default=100.0,
            help=(
                'For OpenAgenda: query bounding box radius around each food truck centroid (km). '
                'Set to 0 to skip geo filter and fetch the whole agenda.'
            ),
        )
        parser.add_argument(
            '--seed-count-per-truck',
            type=int,
            default=8,
            help='Number of synthetic events per active food truck in seed mode.',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=20,
            help='HTTP timeout in seconds.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Compute the sync without writing to database.',
        )

    def handle(self, *args, **options):
        api_key = options['api_key'].strip() or _get_env('OPENAGENDA_API_KEY')
        agenda_uids_raw = options['agenda_uids'].strip() or _get_env('OPENAGENDA_AGENDA_UIDS')
        agenda_uids = [u.strip() for u in agenda_uids_raw.split(',') if u.strip()]
        if not agenda_uids:
            agenda_uids = list(
                OpenAgendaSource.objects
                .filter(is_active=True)
                .values_list('agenda_uid', flat=True)
            )
        source_url = options['source_url'].strip() or _get_env('ANALYTICS_EVENTS_SOURCE_URL')
        mode = options['mode']
        horizon_days = max(1, options['horizon_days'])
        geo_radius_km = max(0.0, options['geo_radius_km'])
        seed_count = max(1, options['seed_count_per_truck'])
        timeout = max(3, options['timeout'])
        dry_run = options['dry_run']

        # Resolve auto mode
        if mode == 'auto':
            if api_key and agenda_uids:
                mode = 'openagenda'
            elif source_url:
                mode = 'fetch'
            else:
                mode = 'seed'

        if mode == 'openagenda' and not api_key:
            raise CommandError(
                '--mode=openagenda requires --api-key or OPENAGENDA_API_KEY env var.'
            )
        if mode == 'openagenda' and not agenda_uids:
            raise CommandError(
                '--mode=openagenda requires agenda UIDs from one of: '
                '--agenda-uids, OPENAGENDA_AGENDA_UIDS, or active OpenAgendaSource rows in database.'
            )
        if mode == 'fetch' and not source_url:
            raise CommandError('--mode=fetch requires --source-url or ANALYTICS_EVENTS_SOURCE_URL.')

        if mode == 'openagenda':
            events_payload, source_label = self._fetch_openagenda(
                api_key=api_key,
                agenda_uids=agenda_uids,
                horizon_days=horizon_days,
                geo_radius_km=geo_radius_km,
                timeout=timeout,
            )
        elif mode == 'fetch':
            events_payload = self._fetch_json_url(source_url, timeout=timeout)
            source_label = f'fetch:{source_url}'
        else:
            events_payload = self._generate_seed_events(seed_count=seed_count, horizon_days=horizon_days)
            source_label = f'seed:{seed_count}/truck/{horizon_days}d'

        created, updated, skipped = self._upsert_events(events_payload, dry_run=dry_run)

        self.stdout.write(self.style.SUCCESS(
            f'sync_events done ({source_label}) '
            f'created={created} updated={updated} skipped={skipped} dry_run={dry_run}'
        ))

    # ------------------------------------------------------------------
    # OpenAgenda
    # ------------------------------------------------------------------

    def _fetch_openagenda(self, api_key, agenda_uids, horizon_days, geo_radius_km, timeout):
        """Fetch upcoming events from one or more OpenAgenda agendas."""
        today = timezone.localdate()
        date_gte = today.isoformat() + 'T00:00:00.000Z'
        date_lte = (today + timedelta(days=horizon_days)).isoformat() + 'T23:59:59.000Z'

        geo_bbox = None
        if geo_radius_km > 0:
            geo_bbox = self._compute_geo_bbox(geo_radius_km)

        all_events = []
        for agenda_uid in agenda_uids:
            fetched = self._fetch_openagenda_agenda(
                api_key=api_key,
                agenda_uid=agenda_uid,
                date_gte=date_gte,
                date_lte=date_lte,
                geo_bbox=geo_bbox,
                timeout=timeout,
            )
            all_events.extend(fetched)
            self.stdout.write(f'  Agenda {agenda_uid}: {len(fetched)} events fetched')

        payload = [self._normalize_openagenda_event(e) for e in all_events]
        payload = [p for p in payload if p is not None]
        source_label = f'openagenda:agendas={",".join(agenda_uids)}'
        return payload, source_label

    def _fetch_openagenda_agenda(self, api_key, agenda_uid, date_gte, date_lte, geo_bbox, timeout):
        """Paginate through all events of a single OpenAgenda agenda."""
        base_url = f'https://api.openagenda.com/v2/agendas/{agenda_uid}/events'
        results = []
        after = None

        while True:
            params_list = [
                ('size', 100),
                ('relative[]', 'upcoming'),
                ('timings[gte]', date_gte),
                ('timings[lte]', date_lte),
                ('monolingual', 'fr'),
                ('includeFields[]', 'uid'),
                ('includeFields[]', 'slug'),
                ('includeFields[]', 'title'),
                ('includeFields[]', 'description'),
                ('includeFields[]', 'longDescription'),
                ('includeFields[]', 'canonicalUrl'),
                ('includeFields[]', 'image'),
                ('includeFields[]', 'keywords'),
                ('includeFields[]', 'timings'),
                ('includeFields[]', 'location.name'),
                ('includeFields[]', 'location.address'),
                ('includeFields[]', 'location.city'),
                ('includeFields[]', 'location.latitude'),
                ('includeFields[]', 'location.longitude'),
            ]
            if geo_bbox:
                params_list += [
                    ('geo[northEast][lat]', geo_bbox['north']),
                    ('geo[northEast][lng]', geo_bbox['east']),
                    ('geo[southWest][lat]', geo_bbox['south']),
                    ('geo[southWest][lng]', geo_bbox['west']),
                ]
            if after:
                for i, val in enumerate(after):
                    params_list.append((f'after[{i}]', val))

            url = base_url + '?' + urlencode(params_list)
            request = Request(url, headers={'key': api_key, 'User-Agent': 'foodtruck-sync-events/1.0'})

            try:
                with _safe_urlopen(request, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
            except HTTPError as exc:
                raise CommandError(f'OpenAgenda HTTP error {exc.code} for agenda {agenda_uid}') from exc
            except URLError as exc:
                raise CommandError(f'OpenAgenda URL error for agenda {agenda_uid}: {exc.reason}') from exc

            events = data.get('events') or []
            for event in events:
                if isinstance(event, dict):
                    event['_agenda_uid'] = agenda_uid
            results.extend(events)

            after = data.get('after')
            if not after or not events:
                break

        return results

    def _compute_geo_bbox(self, radius_km):
        """Compute a bounding box around the centroid of all active food truck positions."""
        trucks = (
            FoodTruck.objects
            .filter(is_active=True)
            .exclude(latitude__isnull=True)
            .exclude(longitude__isnull=True)
        )
        if not trucks.exists():
            return None

        lats = [float(t.latitude) for t in trucks]
        lngs = [float(t.longitude) for t in trucks]
        center_lat = sum(lats) / len(lats)
        center_lng = sum(lngs) / len(lngs)

        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * math.cos(math.radians(center_lat)))

        return {
            'north': center_lat + lat_delta,
            'south': center_lat - lat_delta,
            'east': center_lng + lng_delta,
            'west': center_lng - lng_delta,
        }

    def _normalize_openagenda_event(self, raw):
        """Map an OpenAgenda event object to our internal format."""
        def _pick_text(value):
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, dict):
                return (
                    (value.get('fr') if isinstance(value.get('fr'), str) else None)
                    or next((v for v in value.values() if isinstance(v, str) and v.strip()), '')
                ).strip()
            return ''

        try:
            title = raw.get('title') or {}
            name = _pick_text(title)

            location = raw.get('location') or {}
            latitude = _to_decimal(location['latitude'])
            longitude = _to_decimal(location['longitude'])

            timings = raw.get('timings') or []
            if not timings:
                return None
            begin_str = timings[0]['begin']
            end_str = timings[-1]['end']

            start_date = datetime.fromisoformat(begin_str.replace('Z', '+00:00')).date()
            end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00')).date()
        except (KeyError, ValueError, TypeError, ArithmeticError, StopIteration):
            return None

        if not name:
            return None
        if end_date < start_date:
            return None

        description = _pick_text(raw.get('description')) or _pick_text(raw.get('longDescription'))
        source_url = str(raw.get('canonicalUrl') or raw.get('url') or '').strip()[:500]

        image_url = ''
        image = raw.get('image')
        if isinstance(image, dict):
            base = str(image.get('base') or '').strip()
            filename = str(image.get('filename') or '').strip()
            if base and filename:
                image_url = f"{base}{filename}"
            else:
                image_url = (
                    base
                    or filename
                    or str(image.get('url') or '').strip()
                )
        elif isinstance(image, str):
            image_url = image.strip()
        image_url = image_url[:500]

        if not source_url:
            agenda_uid = str(raw.get('_agenda_uid') or '').strip()
            event_slug = str(raw.get('slug') or '').strip()
            if agenda_uid and event_slug:
                source_url = f'https://openagenda.com/fr/{agenda_uid}/events/{event_slug}'[:500]
            elif agenda_uid:
                source_url = f'https://openagenda.com/fr/{agenda_uid}'[:500]

        category = ''
        keywords = raw.get('keywords')
        if isinstance(keywords, list) and keywords:
            category = str(keywords[0]).strip()[:64]

        location_name = str(location.get('name') or '').strip()
        location_address = str(location.get('address') or '').strip()
        location_city = str(location.get('city') or '').strip()
        location_text = ', '.join(part for part in [location_name, location_address, location_city] if part)[:255]

        return {
            'name': name,
            'latitude': latitude,
            'longitude': longitude,
            'start_date': start_date,
            'end_date': end_date,
            'expected_attendance': None,
            'description': description,
            'image_url': image_url,
            'source_url': source_url,
            'category': category,
            'location_text': location_text,
        }

    # ------------------------------------------------------------------
    # Generic JSON URL
    # ------------------------------------------------------------------

    def _fetch_json_url(self, source_url, timeout=20):
        request = Request(source_url, headers={'User-Agent': 'foodtruck-sync-events/1.0'})
        try:
            with _safe_urlopen(request, timeout=timeout) as response:
                payload = response.read().decode('utf-8')
        except HTTPError as exc:
            raise CommandError(f'HTTP error while fetching events: {exc.code}') from exc
        except URLError as exc:
            raise CommandError(f'URL error while fetching events: {exc.reason}') from exc

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CommandError('Invalid JSON payload from source URL') from exc

        if not isinstance(parsed, list):
            raise CommandError('JSON payload must be an array of objects')

        return parsed

    # ------------------------------------------------------------------
    # Seed (synthetic dev data)
    # ------------------------------------------------------------------

    def _generate_seed_events(self, seed_count=8, horizon_days=60):
        trucks = (
            FoodTruck.objects
            .filter(is_active=True)
            .exclude(latitude__isnull=True)
            .exclude(longitude__isnull=True)
        )
        if not trucks.exists():
            return []

        base_names = [
            'Street Food Festival',
            'Local Market',
            'Music Night',
            'Business Lunch Fair',
            'Family Sunday Event',
            'Sport Fan Zone',
            'Night Market',
            'Campus Food Day',
        ]

        random.seed(timezone.now().strftime('%Y%m%d'))
        today = timezone.localdate()
        output = []

        for truck in trucks:
            truck_lat = float(truck.latitude)
            truck_lng = float(truck.longitude)
            for idx in range(seed_count):
                day_offset = random.randint(1, horizon_days)
                event_date = today + timedelta(days=day_offset)
                lat_jitter = random.uniform(-0.18, 0.18)
                lng_jitter = random.uniform(-0.22, 0.22)
                output.append({
                    'name': f"{random.choice(base_names)} - {truck.name} #{idx + 1}",
                    'latitude': truck_lat + lat_jitter,
                    'longitude': truck_lng + lng_jitter,
                    'start_date': str(event_date),
                    'end_date': str(event_date),
                    'expected_attendance': random.randint(300, 12000),
                })

        return output

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def _upsert_events(self, events_payload, dry_run=False):
        created = 0
        updated = 0
        skipped = 0

        if not events_payload:
            self.stdout.write('No events to sync.')
            return created, updated, skipped

        with transaction.atomic():
            for raw in events_payload:
                normalized = self._normalize_generic_event(raw)
                if normalized is None:
                    skipped += 1
                    continue

                identity = {
                    'name': normalized['name'],
                    'latitude': normalized['latitude'],
                    'longitude': normalized['longitude'],
                    'start_date': normalized['start_date'],
                    'end_date': normalized['end_date'],
                }

                existing = Event.objects.filter(**identity).first()
                if existing:
                    new_attendance = normalized['expected_attendance']
                    new_location_text = normalized.get('location_text') or ''
                    new_description = normalized.get('description') or ''
                    new_image_url = normalized.get('image_url') or ''
                    new_source_url = normalized.get('source_url') or ''
                    new_category = normalized.get('category') or ''

                    changed = (
                        existing.expected_attendance != new_attendance
                        or existing.location_text != new_location_text
                        or existing.description != new_description
                        or existing.image_url != new_image_url
                        or existing.source_url != new_source_url
                        or existing.category != new_category
                    )

                    if changed:
                        updated += 1
                        if not dry_run:
                            existing.expected_attendance = new_attendance
                            existing.location_text = new_location_text
                            existing.description = new_description
                            existing.image_url = new_image_url
                            existing.source_url = new_source_url
                            existing.category = new_category
                            existing.save(update_fields=[
                                'expected_attendance',
                                'location_text',
                                'description',
                                'image_url',
                                'source_url',
                                'category',
                            ])
                else:
                    created += 1
                    if not dry_run:
                        Event.objects.create(
                            name=normalized['name'],
                            latitude=normalized['latitude'],
                            longitude=normalized['longitude'],
                            start_date=normalized['start_date'],
                            end_date=normalized['end_date'],
                            expected_attendance=normalized['expected_attendance'],
                            location_text=normalized.get('location_text') or '',
                            description=normalized.get('description') or '',
                            image_url=normalized.get('image_url') or '',
                            source_url=normalized.get('source_url') or '',
                            category=normalized.get('category') or '',
                        )

            if dry_run:
                transaction.set_rollback(True)

        return created, updated, skipped

    def _normalize_generic_event(self, raw):
        """Normalize a generic dict (from fetch mode or pre-normalized openagenda output)."""
        # Already normalized by _normalize_openagenda_event (date objects present)
        if 'start_date' in raw and not isinstance(raw.get('start_date'), str):
            return raw

        try:
            name = str(raw['name']).strip()
            latitude = _to_decimal(raw['latitude'])
            longitude = _to_decimal(raw['longitude'])
            start_date = datetime.fromisoformat(str(raw['start_date'])).date()
            end_date = datetime.fromisoformat(str(raw['end_date'])).date()
            expected_attendance = raw.get('expected_attendance')
            expected_attendance = int(expected_attendance) if expected_attendance is not None else None
            location_text = str(raw.get('location_text') or '').strip()[:255]
            description = str(raw.get('description') or '').strip()
            image_url = str(raw.get('image_url') or '').strip()[:500]
            source_url = str(raw.get('source_url') or '').strip()[:500]
            category = str(raw.get('category') or '').strip()[:64]
        except (KeyError, ValueError, TypeError, ArithmeticError):
            return None

        if not name:
            return None
        if end_date < start_date:
            return None

        return {
            'name': name,
            'latitude': latitude,
            'longitude': longitude,
            'start_date': start_date,
            'end_date': end_date,
            'expected_attendance': expected_attendance,
            'location_text': location_text,
            'description': description,
            'image_url': image_url,
            'source_url': source_url,
            'category': category,
        }
