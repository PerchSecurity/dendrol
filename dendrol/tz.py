from datetime import tzinfo, timedelta


class utc(tzinfo):
    def tzname(self,**kwargs):
        return 'UTC'

    def utcoffset(self, dt):
        return timedelta(0)
