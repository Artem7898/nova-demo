from django.core.management.base import BaseCommand, CommandError

from catalog.lab.registry import SCENARIOS
from catalog.lab.runner import run_scenario


class Command(BaseCommand):
    help = "Run all Nova Demo scenarios against the installed package; fail on real errors."

    def add_arguments(self, parser):
        parser.add_argument(
            "--require-services", action="store_true", help="Fail if a service is not configured"
        )

    def handle(self, *args, **options):
        failed = []
        for spec in SCENARIOS:
            result = run_scenario(spec["id"], spec["payload"])
            self.stdout.write(
                f"{result['status'].upper():7} {spec['id']}: {result['duration_ms']:.1f} ms"
            )
            if (
                result["status"] == "failed"
                or options["require_services"]
                and result["status"] == "skipped"
            ):
                failed.append(spec["id"])
                self.stdout.write(str(result["output"]))
        if failed:
            raise CommandError("Failed: " + ", ".join(failed))
