"""Route blueprints, one per section of the site."""
from routes import (auth, campus_map, dashboard, events, grades, lift_up_vikes, search, settings, spaces,
                    mobile_campus, orientation, schedule, transportation,
                    viking_card)

ALL_BLUEPRINTS = [
    auth.bp,
    dashboard.bp,
    viking_card.bp,
    orientation.bp,
    schedule.bp,
    grades.bp,
    campus_map.bp,
    transportation.bp,
    events.bp,
    mobile_campus.bp,
    lift_up_vikes.bp,
    spaces.bp,
    search.bp,
    settings.bp,
]
