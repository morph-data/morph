import os
import time


class TimezoneManager:
    def __init__(self):
        self.zone_dir = "/usr/share/zoneinfo"

    def list_timezones(self):
        if not os.path.isdir(self.zone_dir):
            return []

        timezones = []
        for root, dirs, files in os.walk(self.zone_dir):
            for name in files:
                filepath = os.path.join(root, name)
                # Skip symlinks and irrelevant files
                if os.path.islink(filepath) or name in ["posixrules", "localtime"]:
                    continue

                # Convert the file path into a timezone format (e.g., "Asia/Tokyo")
                timezone = os.path.relpath(filepath, self.zone_dir)
                timezones.append(timezone)

        return sorted(timezones)

    def is_valid_timezone(self, timezone):
        return timezone in self.list_timezones()

    @staticmethod
    def set_timezone(timezone: str) -> None:
        os.environ["TZ"] = timezone
        time.tzset()
