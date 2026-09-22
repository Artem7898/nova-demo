from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import DemoWorkspace


class Command(BaseCommand):
    help = "Delete expired anonymous demo workspaces only; existing catalog rows are untouched."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=max(1, options["days"]))
        qs = DemoWorkspace.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        if not options["dry_run"]:
            qs.delete()
        self.stdout.write(
            f"{'Would remove' if options['dry_run'] else 'Removed'} {count} demo workspaces"
        )
