# ShareaSpot - Demo Data Seeder
# Run with: python seed_data.py

import json, uuid, hashlib
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import Base, User, Post, Tag, Category, Like, Follow

engine = create_engine("sqlite:///./shareaspot.db", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
db = Session()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def tok(): return uuid.uuid4().hex

# ── Demo Users ────────────────────────────────────────────────────────────
users_data = [
    ("maya_shoots",   "maya@demo.com",    "demo1234", "Landscape & street photographer based in NYC 📸"),
    ("wanderlust_kai","kai@demo.com",     "demo1234", "Always chasing the next horizon 🥾"),
    ("urban_eats",    "eats@demo.com",    "demo1234", "Food blogger | Hidden gems only 🍽️"),
    ("golden.lens",   "golden@demo.com",  "demo1234", "Sunrise addict. Sunset chaser 🌅"),
    ("cityvibes_",    "city@demo.com",    "demo1234", "Urban explorer | Architecture nerd 🏙️"),
]

created_users = []
for username, email, pw, bio in users_data:
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        created_users.append(existing)
    else:
        u = User(username=username, email=email, password_hash=hash_pw(pw), bio=bio, token=tok())
        db.add(u)
        db.flush()
        created_users.append(u)

db.commit()
print(f"✓ {len(created_users)} demo users ready")

# ── Helper: get category by name ──────────────────────────────────────────
def cat(name):
    return db.query(Category).filter(Category.name == name).first()

def get_or_create_tag(name):
    t = db.query(Tag).filter(Tag.name == name).first()
    if not t:
        t = Tag(name=name)
        db.add(t)
        db.flush()
    return t

# ── Demo Posts (with real coordinates) ───────────────────────────────────
posts_data = [
    {
        "user": created_users[0],  # maya_shoots
        "title": "Brooklyn Bridge at Blue Hour",
        "description": "Catch this spot just before sunrise for that perfect blue-to-orange gradient reflecting off the East River. Get there 30 mins early to claim your position on the pedestrian walkway. Tripod essential.",
        "address_street": "Brooklyn Bridge Pedestrian Walkway",
        "address_city": "Brooklyn",
        "address_state": "NY",
        "location_zip": "11201",
        "location_name": "Brooklyn, NY",
        "lat": 40.7061, "lng": -73.9969,
        "tags": ["blue-hour", "architecture", "bridge", "long-exposure"],
        "categories": ["For Photographers", "For Influencers"],
        "ago_days": 2,
    },
    {
        "user": created_users[1],  # wanderlust_kai
        "title": "Secret Overlook Trail",
        "description": "Lesser known trail that leads to a stunning 180° view of the valley. The last mile is steep but worth every step. Best in fall when the leaves turn. Bring water — no facilities on trail.",
        "address_street": "Overlook Trail Head, Old Mill Rd",
        "address_city": "Asheville",
        "address_state": "NC",
        "location_zip": "28801",
        "location_name": "Asheville, NC",
        "lat": 35.5951, "lng": -82.5515,
        "tags": ["hiking", "valley-view", "fall-foliage", "hidden-gem"],
        "categories": ["For Hikers", "For Photographers", "For Sunrise/Sunset"],
        "ago_days": 5,
    },
    {
        "user": created_users[2],  # urban_eats
        "title": "The Underground Ramen Bar",
        "description": "Literally underground — down a flight of stairs from street level. 12-hour broth, hand-pulled noodles, and a lineup of small plates that changes weekly. Cash only, limited seating, worth the wait.",
        "address_street": "42 Orchard St",
        "address_city": "New York",
        "address_state": "NY",
        "location_zip": "10002",
        "location_name": "Lower East Side, NYC",
        "lat": 40.7151, "lng": -73.9901,
        "tags": ["ramen", "hidden-gem", "cash-only", "small-plates"],
        "categories": ["For Foodies", "For Influencers"],
        "ago_days": 1,
    },
    {
        "user": created_users[3],  # golden.lens
        "title": "Pacific Bluff Sunrise Point",
        "description": "Unobstructed eastern horizon — rare on the West Coast. You get dramatic sea-stack silhouettes against the morning sky. Park on the gravel lot off Hwy 1, then a 10-min walk through low scrub.",
        "address_street": "Unnamed Bluff Access, Hwy 1",
        "address_city": "Half Moon Bay",
        "address_state": "CA",
        "location_zip": "94019",
        "location_name": "Half Moon Bay, CA",
        "lat": 37.4636, "lng": -122.4286,
        "tags": ["sunrise", "sea-stacks", "coastal", "golden-hour"],
        "categories": ["For Sunrise/Sunset", "For Photographers"],
        "ago_days": 3,
    },
    {
        "user": created_users[4],  # cityvibes_
        "title": "The Forgotten Freight Alley",
        "description": "Old rail freight alley turned into a graffiti corridor. New murals go up constantly so it always looks different. Great leading lines for street photography and incredible colour even on overcast days.",
        "address_street": "Freight Alley, off N Halsted St",
        "address_city": "Chicago",
        "address_state": "IL",
        "location_zip": "60614",
        "location_name": "Lincoln Park, Chicago",
        "lat": 41.9245, "lng": -87.6491,
        "tags": ["street-art", "murals", "urban", "graffiti"],
        "categories": ["For Urban Explorers", "For Artists", "For Photographers"],
        "ago_days": 7,
    },
    {
        "user": created_users[0],  # maya_shoots
        "title": "Rooftop Garden — Midtown",
        "description": "Public rooftop garden open April–October, free entry. Stunning midtown skyline backdrop. Best light 4–6pm when the afternoon sun hits the towers. Gets busy on weekends so go Tuesday/Wednesday.",
        "address_street": "230 W 39th St, Rooftop",
        "address_city": "New York",
        "address_state": "NY",
        "location_zip": "10018",
        "location_name": "Midtown Manhattan, NYC",
        "lat": 40.7549, "lng": -73.9940,
        "tags": ["rooftop", "skyline", "gardens", "free"],
        "categories": ["For Photographers", "For Influencers", "For Wellness"],
        "ago_days": 10,
    },
    {
        "user": created_users[1],  # wanderlust_kai
        "title": "Slot Canyon Day Hike",
        "description": "Narrow sandstone slot canyon carved by flash floods. The light beams at midday (11am–1pm) are otherworldly. Book permits in advance — they sell out weeks ahead in summer. No flash photography.",
        "address_street": "Canyon Tours Trailhead, Navajo Rd",
        "address_city": "Page",
        "address_state": "AZ",
        "location_zip": "86040",
        "location_name": "Page, AZ",
        "lat": 36.9147, "lng": -111.4558,
        "tags": ["canyon", "light-beams", "desert", "permit-required"],
        "categories": ["For Hikers", "For Photographers"],
        "ago_days": 14,
    },
    {
        "user": created_users[2],  # urban_eats
        "title": "Farmers Market at Civic Center",
        "description": "Saturday mornings only, 7am–2pm. Best tamales in the city, incredible seasonal produce, and a hot sauce vendor that will set your soul on fire in the best way. Get there early — the good stuff goes fast.",
        "address_street": "Civic Center Plaza",
        "address_city": "San Francisco",
        "address_state": "CA",
        "location_zip": "94102",
        "location_name": "Civic Center, SF",
        "lat": 37.7793, "lng": -122.4193,
        "tags": ["farmers-market", "saturday-only", "street-food", "fresh"],
        "categories": ["For Foodies", "For Families"],
        "ago_days": 4,
    },
]

created_posts = 0
updated_coords = 0
for pd in posts_data:
    existing = db.query(Post).filter(Post.title == pd["title"]).first()
    if existing:
        # Update coordinates on existing posts that are missing them
        if existing.lat is None and pd.get("lat"):
            existing.lat = pd["lat"]
            existing.lng = pd["lng"]
            updated_coords += 1
        continue

    post = Post(
        user_id=pd["user"].id,
        title=pd["title"],
        description=pd["description"],
        address_street=pd["address_street"],
        address_city=pd["address_city"],
        address_state=pd["address_state"],
        location_zip=pd["location_zip"],
        location_name=pd["location_name"],
        lat=pd.get("lat"),
        lng=pd.get("lng"),
        photos=json.dumps([]),
        created_at=datetime.utcnow() - timedelta(days=pd["ago_days"]),
    )

    for tag_name in pd["tags"]:
        post.tags.append(get_or_create_tag(tag_name))

    for cat_name in pd["categories"]:
        c = cat(cat_name)
        if c:
            post.categories.append(c)

    db.add(post)
    created_posts += 1

db.commit()
print(f"✓ {created_posts} demo posts added, {updated_coords} existing posts updated with coordinates")

# ── Demo Likes ────────────────────────────────────────────────────────────
posts = db.query(Post).all()
like_pairs = [
    (created_users[1], posts[0]),
    (created_users[2], posts[0]),
    (created_users[3], posts[0]),
    (created_users[0], posts[1]),
    (created_users[4], posts[1]),
    (created_users[0], posts[2]),
    (created_users[1], posts[3]),
    (created_users[2], posts[3]),
    (created_users[4], posts[4]),
    (created_users[0], posts[4]),
    (created_users[3], posts[5]),
    (created_users[1], posts[6]),
]

likes_added = 0
for user, post in like_pairs:
    from main import Like
    existing = db.query(Like).filter(Like.user_id == user.id, Like.post_id == post.id).first()
    if not existing:
        db.add(Like(user_id=user.id, post_id=post.id))
        likes_added += 1

db.commit()
print(f"✓ {likes_added} demo likes added")

# ── Demo Follows ──────────────────────────────────────────────────────────
follow_pairs = [
    (created_users[0], created_users[3]),
    (created_users[0], created_users[4]),
    (created_users[1], created_users[0]),
    (created_users[2], created_users[0]),
    (created_users[3], created_users[0]),
    (created_users[4], created_users[1]),
]

follows_added = 0
for follower, following in follow_pairs:
    from main import Follow
    existing = db.query(Follow).filter(Follow.follower_id == follower.id, Follow.following_id == following.id).first()
    if not existing:
        db.add(Follow(follower_id=follower.id, following_id=following.id))
        follows_added += 1

db.commit()
print(f"✓ {follows_added} demo follows added")

db.close()
print("\n✅ Done! Refresh the app and click 🗺 Map to see all pins.")
print("\nDemo accounts (password: demo1234):")
for u in created_users:
    print(f"   @{u.username}")
