import os
import time


class TimezoneManager:
    def __init__(self):
        self.zone_dir = self._get_zone_dir()

    @staticmethod
    def _get_zone_dir():
        localtime_link = os.readlink("/etc/localtime")
        zone_dir = os.path.dirname(localtime_link)
        if "zoneinfo" in zone_dir:
            return zone_dir.split("zoneinfo")[0] + "zoneinfo"
        else:
            return "/usr/share/zoneinfo"

    @staticmethod
    def get_current_timezone():
        localtime_link = os.readlink("/etc/localtime")
        return localtime_link.split("zoneinfo/")[-1]

    def list_timezones(self):
        timezones = []
        for root, dirs, files in os.walk(self.zone_dir):
            for name in files:
                filepath = os.path.join(root, name)
                if not os.path.islink(filepath) and name not in [
                    "posixrules",
                    "localtime",
                ]:
                    timezone = os.path.relpath(filepath, self.zone_dir)
                    timezones.append(timezone)
        return sorted(timezones)

    def is_valid_timezone(self, timezone):
        return timezone in self.list_timezones()

    @staticmethod
    def set_timezone(timezone: str) -> None:
        os.environ["TZ"] = timezone
        time.tzset()
