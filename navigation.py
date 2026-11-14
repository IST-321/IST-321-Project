"""Navigation lists shared by the menu, the bottom bar and search."""

# Student services, in the order they appear on the home screen.
# "mobile" items also appear in the bottom bar on phones.
SERVICES = [
    {"endpoint": "orientation.index", "label": "Orientation", "short": "Orientation", "icon": "flag",
     "blurb": "Your checklist for getting started at CSU", "mobile": False},
    {"endpoint": "viking_card.index", "label": "Viking Card", "short": "Card", "icon": "card",
     "blurb": "Balance, activity, meal plan and card controls", "mobile": True},
    {"endpoint": "schedule.index", "label": "Schedule", "short": "Schedule", "icon": "calendar",
     "blurb": "Classes, deadlines and personal events", "mobile": True},
    {"endpoint": "campus_map.index", "label": "Campus map", "short": "Map", "icon": "map",
     "blurb": "Buildings, offices and classrooms", "mobile": False},
    {"endpoint": "events.index", "label": "Events and VikesConnect", "short": "Events", "icon": "ticket",
     "blurb": "Campus events and student organizations", "mobile": False},
    {"endpoint": "mobile_campus.index", "label": "Mobile Campus", "short": "Devices", "icon": "laptop",
     "blurb": "Borrow a laptop, calculator or other equipment", "mobile": False},
    {"endpoint": "spaces.index", "label": "Book a space", "short": "Spaces", "icon": "door",
     "blurb": "Library study rooms and Rec Center classes", "mobile": False},
    {"endpoint": "lift_up_vikes.index", "label": "Lift Up Vikes", "short": "Pantry", "icon": "basket",
     "blurb": "Food pantry appointments and support", "mobile": False},
]

# The Getting around group in the menu. The first one is also in the bottom bar on phones.
GETTING_AROUND = [
    {"endpoint": "transportation.parking", "label": "Parking garages and permits", "short": "Parking", "icon": "building"},
    {"endpoint": "transportation.trip", "label": "Plan a trip", "short": "Trips", "icon": "bus"},
    {"endpoint": "transportation.escorts", "label": "Viking Safety Escorts", "short": "Escorts", "icon": "shield"},
    {"endpoint": "transportation.reports", "label": "Report an issue", "short": "Report", "icon": "warning"},
]

# Takes Orientation's place in the menu once every orientation step is complete
RESOURCES_LINK = {"endpoint": "orientation.resources_page", "label": "Resources", "short": "Resources", "icon": "book",
                  "blurb": "First semester resources and the new student directory", "mobile": False}
