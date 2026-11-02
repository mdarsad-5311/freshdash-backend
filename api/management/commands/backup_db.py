import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Perform a safe, online hot-backup of the production SQLite3 database without locking active queries."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Custom output path for the backup file. Defaults to BASE_DIR/backups/freshdash_backup_TIMESTAMP.sqlite3'
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=7,
            help='Number of days of daily backups to retain (older backups will be pruned). Defaults to 7.'
        )

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES['default']['NAME']).resolve()
        if not db_path.exists():
            raise CommandError(f"Database file does not exist at: {db_path}")

        # Destination backup directory
        backup_dir = settings.BASE_DIR / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if options['output']:
            target_path = Path(options['output']).resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            target_path = backup_dir / f"freshdash_backup_{timestamp}.sqlite3"

        self.stdout.write(f"Initiating safe hot backup of {db_path.name}...")
        start_time = time.time()

        try:
            # Use SQLite's online backup API for safe, concurrent hot snapshot
            source_conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            target_conn = sqlite3.connect(str(target_path))

            with target_conn:
                source_conn.backup(target_conn, pages=100)

            source_conn.close()
            target_conn.close()

            elapsed = time.time() - start_time
            file_size_kb = target_path.stat().st_size / 1024

            self.stdout.write(
                self.style.SUCCESS(
                    f"Backup completed successfully!\n"
                    f"  Destination: {target_path}\n"
                    f"  Size: {file_size_kb:.2f} KB\n"
                    f"  Elapsed: {elapsed:.2f}s"
                )
            )
        except Exception as e:
            raise CommandError(f"Failed to perform backup: {e}")

        # Prune old backups
        keep_days = options['keep_days']
        if keep_days > 0 and not options['output']:
            now = time.time()
            cutoff = now - (keep_days * 86400)
            pruned_count = 0
            for backup_file in backup_dir.glob("freshdash_backup_*.sqlite3"):
                if backup_file.is_file() and backup_file.stat().st_mtime < cutoff:
                    try:
                        backup_file.unlink()
                        pruned_count += 1
                    except OSError:
                        pass
            if pruned_count > 0:
                self.stdout.write(f"Cleaned up {pruned_count} backup(s) older than {keep_days} days.")

