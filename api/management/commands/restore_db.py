import sqlite3
import shutil
import time
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Safely restore the active SQLite3 database from a backup file, taking an automatic safety snapshot first."

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            type=str,
            help='Path to the .sqlite3 backup file to restore from.'
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not prompt for interactive confirmation before restoring.'
        )

    def handle(self, *args, **options):
        backup_file = Path(options['backup_file']).resolve()
        if not backup_file.exists() or not backup_file.is_file():
            raise CommandError(f"Backup file not found: {backup_file}")

        # Quick validation of backup file integrity
        try:
            test_conn = sqlite3.connect(f"file:{backup_file}?mode=ro", uri=True)
            cur = test_conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            status = cur.fetchone()[0]
            test_conn.close()
            if status != "ok":
                raise CommandError(f"Backup file failed integrity check: {status}")
        except Exception as err:
            raise CommandError(f"Cannot read backup file: {err}")

        active_db = Path(settings.DATABASES['default']['NAME']).resolve()

        if not options['no_input']:
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: This will replace the current active database:\n"
                    f"  Active DB: {active_db}\n"
                    f"  With backup: {backup_file}\n"
                )
            )
            confirm = input("Are you sure you want to proceed with restore? [y/N]: ").strip().lower()
            if confirm not in ('y', 'yes'):
                self.stdout.write("Restore operation cancelled by user.")
                return

        # Create safety pre-restore backup
        if active_db.exists():
            safety_dir = settings.BASE_DIR / 'backups' / 'safety_pre_restore'
            safety_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safety_path = safety_dir / f"safety_before_restore_{timestamp}.sqlite3"

            self.stdout.write("Creating automatic safety snapshot before restore...")
            src = sqlite3.connect(f"file:{active_db}?mode=ro", uri=True)
            dst = sqlite3.connect(str(safety_path))
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
            self.stdout.write(f"Safety snapshot saved to: {safety_path}")

        # Perform restore
        self.stdout.write(f"Restoring database from {backup_file.name}...")
        try:
            # Clean up WAL/SHM temporary files if active
            wal_file = Path(f"{active_db}-wal")
            shm_file = Path(f"{active_db}-shm")
            if wal_file.exists():
                try: wal_file.unlink()
                except OSError: pass
            if shm_file.exists():
                try: shm_file.unlink()
                except OSError: pass

            shutil.copy2(backup_file, active_db)

            # Verify restored database
            verify_conn = sqlite3.connect(str(active_db))
            cur = verify_conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            integrity = cur.fetchone()[0]
            verify_conn.close()

            if integrity != "ok":
                raise CommandError(f"Restored database integrity check failed: {integrity}")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Database restored successfully!\n"
                    f"  Active database: {active_db}\n"
                    f"  Integrity: OK"
                )
            )
        except Exception as e:
            raise CommandError(f"Restore failed: {e}")

