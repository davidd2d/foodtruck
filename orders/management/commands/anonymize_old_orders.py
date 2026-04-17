from django.core.management.base import BaseCommand

from orders.services import DataRetentionService


class Command(BaseCommand):
    help = 'Anonymize paid orders older than the configured retention threshold.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90)
        parser.add_argument('--batch-size', type=int, default=500)

    def handle(self, *args, **options):
        anonymized = DataRetentionService.anonymize_old_orders(
            days=options['days'],
            batch_size=options['batch_size'],
        )
        self.stdout.write(self.style.SUCCESS(f'Anonymized {anonymized} order(s).'))