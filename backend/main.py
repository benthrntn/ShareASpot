# ShareaSpot - Social Media Location App
# Run with: uvicorn main:app --reload

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Table, UniqueConstraint, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import hashlib, os, uuid, shutil, json, urllib.request, urllib.parse, boto3
from botocore.config import Config

# ── Database Setup ──────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./shareaspot.db")
# Render provides postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── R2 Storage Setup ────────────────────────────────────────────────────────
R2_ACCOUNT_ID    = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY    = os.environ.get("R2_ACCESS_KEY", "")
R2_SECRET_KEY    = os.environ.get("R2_SECRET_KEY", "")
R2_BUCKET        = os.environ.get("R2_BUCKET", "shareaspot")
R2_PUBLIC_URL    = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
USE_R2           = all([R2_ACCOUNT_ID, R2_ACCESS_KEY, R2_SECRET_KEY, R2_PUBLIC_URL])

if USE_R2:
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

# Local fallback for development
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

def upload_file(file_bytes: bytes, fname: str, content_type: str = "image/jpeg") -> str:
    """Upload to R2 if configured, otherwise save locally. Returns public URL."""
    if USE_R2:
        s3.put_object(Bucket=R2_BUCKET, Key=fname, Body=file_bytes, ContentType=content_type)
        return f"{R2_PUBLIC_URL}/{fname}"
    else:
        with open(UPLOAD_DIR / fname, "wb") as f:
            f.write(file_bytes)
        return f"/uploads/{fname}"

def delete_file(fname: str):
    """Delete from R2 if configured, otherwise delete locally."""
    if USE_R2:
        try:
            s3.delete_object(Bucket=R2_BUCKET, Key=fname)
        except Exception:
            pass
    else:
        fp = UPLOAD_DIR / fname
        if fp.exists():
            fp.unlink()

# ── Association Tables ───────────────────────────────────────────────────────
post_tags = Table("post_tags", Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id")),
    Column("tag_id",  Integer, ForeignKey("tags.id")),
)
post_categories = Table("post_categories", Base.metadata,
    Column("post_id",     Integer, ForeignKey("posts.id")),
    Column("category_id", Integer, ForeignKey("categories.id")),
)

# ── ORM Models ───────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True)
    username      = Column(String,  unique=True, index=True)
    email         = Column(String,  unique=True, index=True)
    password_hash = Column(String)
    bio           = Column(Text, default="")
    avatar        = Column(String, nullable=True)
    token         = Column(String, unique=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    posts         = relationship("Post", back_populates="author")
    likes         = relationship("Like", back_populates="user")
    comments      = relationship("Comment", back_populates="author", foreign_keys="Comment.user_id")
    notifications = relationship("Notification", back_populates="recipient", foreign_keys="Notification.user_id")
    # follows where this user is the follower
    following     = relationship("Follow", foreign_keys="Follow.follower_id", back_populates="follower")
    # follows where this user is being followed
    followers     = relationship("Follow", foreign_keys="Follow.following_id", back_populates="following")

class Post(Base):
    __tablename__ = "posts"
    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"))
    title           = Column(String)
    description     = Column(Text)
    # Full address fields
    address_street  = Column(String, default="")
    address_city    = Column(String, default="")
    address_state   = Column(String, default="")
    location_zip    = Column(String)
    location_name   = Column(String)
    lat             = Column(Float, nullable=True)
    lng             = Column(Float, nullable=True)
    photos          = Column(Text)   # JSON list of filenames
    created_at      = Column(DateTime, default=datetime.utcnow)
    author          = relationship("User", back_populates="posts")
    tags            = relationship("Tag",      secondary=post_tags,       back_populates="posts")
    categories      = relationship("Category", secondary=post_categories, back_populates="posts")
    likes           = relationship("Like", back_populates="post")
    comments        = relationship("Comment", back_populates="post", cascade="all, delete-orphan",
                                   order_by="Comment.created_at")

class Tag(Base):
    __tablename__ = "tags"
    id    = Column(Integer, primary_key=True)
    name  = Column(String, unique=True)
    posts = relationship("Post", secondary=post_tags, back_populates="tags")

class Category(Base):
    __tablename__ = "categories"
    id    = Column(Integer, primary_key=True)
    name  = Column(String, unique=True)
    icon  = Column(String)
    posts = relationship("Post", secondary=post_categories, back_populates="categories")

class Like(Base):
    __tablename__ = "likes"
    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    user    = relationship("User", back_populates="likes")
    post    = relationship("Post", back_populates="likes")

class Follow(Base):
    __tablename__  = "follows"
    id             = Column(Integer, primary_key=True)
    follower_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    following_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow)
    follower       = relationship("User", foreign_keys=[follower_id],  back_populates="following")
    following      = relationship("User", foreign_keys=[following_id], back_populates="followers")
    __table_args__ = (UniqueConstraint("follower_id", "following_id", name="uq_follow"),)

class Comment(Base):
    __tablename__ = "comments"
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id    = Column(Integer, ForeignKey("posts.id"), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    author     = relationship("User", back_populates="comments", foreign_keys=[user_id])
    post       = relationship("Post", back_populates="comments")

class Notification(Base):
    __tablename__ = "notifications"
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)   # recipient
    actor_id   = Column(Integer, ForeignKey("users.id"), nullable=False)   # who did it
    type       = Column(String, nullable=False)  # 'follow' | 'like' | 'comment'
    post_id    = Column(Integer, ForeignKey("posts.id"), nullable=True)
    read       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    recipient  = relationship("User", back_populates="notifications", foreign_keys=[user_id])
    actor      = relationship("User", foreign_keys=[actor_id])

Base.metadata.create_all(bind=engine)

# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(title="ShareaSpot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")

# ── Helpers ──────────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def gen_token() -> str:
    return uuid.uuid4().hex

def require_user(token: str, db: Session):
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(401, "Invalid or missing token")
    return user

def geocode(address: str):
    """Geocode using Nominatim via urllib only. Returns (lat, lng) or (None, None)."""
    try:
        params = urllib.parse.urlencode({"q": address, "format": "json", "limit": "1"})
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "ShareaSpot/1.0 (shareaspot-app)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None, None

def notify(db: Session, user_id: int, actor_id: int, type_: str, post_id: int = None):
    """Create a notification if user_id != actor_id."""
    if user_id == actor_id:
        return
    notif = Notification(
        user_id=user_id,
        actor_id=actor_id,
        type=type_,
        post_id=post_id,
    )
    db.add(notif)

def serialize_post(post: Post, current_user_id: int = None):
    photos = json.loads(post.photos) if post.photos else []
    return {
        "id":             post.id,
        "title":          post.title,
        "description":    post.description,
        "address_street": post.address_street or "",
        "address_city":   post.address_city   or "",
        "address_state":  post.address_state  or "",
        "location_zip":   post.location_zip,
        "location_name":  post.location_name,
        "lat":            post.lat,
        "lng":            post.lng,
        "photos":         [p if p.startswith("http") else f"/uploads/{p}" for p in photos],
        "author":         {
            "id":       post.author.id,
            "username": post.author.username,
            "avatar":   post.author.avatar if (post.author.avatar and post.author.avatar.startswith("http")) else (f"/uploads/{post.author.avatar}" if post.author.avatar else None),
        },
        "tags":           [t.name for t in post.tags],
        "categories":     [{"id": c.id, "name": c.name, "icon": c.icon} for c in post.categories],
        "likes":          len(post.likes) if post.likes is not None else 0,
        "liked_by_me":    any(l.user_id == current_user_id for l in post.likes) if (current_user_id and post.likes) else False,
        "comment_count":  len(post.comments) if post.comments is not None else 0,
        "is_mine":        post.user_id == current_user_id if current_user_id else False,
        "created_at":     post.created_at.isoformat(),
    }

def serialize_user(user: User, current_user_id: int = None, db: Session = None):
    is_following = False
    if current_user_id and db:
        is_following = db.query(Follow).filter(
            Follow.follower_id  == current_user_id,
            Follow.following_id == user.id
        ).first() is not None
    return {
        "id":              user.id,
        "username":        user.username,
        "bio":             user.bio or "",
        "avatar":          user.avatar if (user.avatar and user.avatar.startswith("http")) else (f"/uploads/{user.avatar}" if user.avatar else None),
        "post_count":      len(user.posts),
        "follower_count":  len(user.followers),
        "following_count": len(user.following),
        "is_following":    is_following,
        "is_self":         user.id == current_user_id,
    }

# ── Startup: seed + auto-migrate ─────────────────────────────────────────────
CATEGORIES = [
    ("For Photographers",       "📸"),
    ("For Influencers",         "🎥"),
    ("For Hikers",              "🥾"),
    ("For Sunrise/Sunset",      "🌅"),
    ("For Urban Explorers",     "🏙️"),
    ("For Artists",             "🎨"),
    ("For Foodies",             "🍽️"),
    ("For Families",            "👨‍👩‍👧"),
    ("For Wellness",            "🧘"),
]

@app.on_event("startup")
def startup():
    db = SessionLocal()
    # Seed categories
    for name, icon in CATEGORIES:
        if not db.query(Category).filter(Category.name == name).first():
            db.add(Category(name=name, icon=icon))
    db.commit()

    # Auto-migrate: add new columns to existing tables if they don't exist
    migrations = [
        "ALTER TABLE posts ADD COLUMN lat FLOAT",
        "ALTER TABLE posts ADD COLUMN lng FLOAT",
        "ALTER TABLE users ADD COLUMN avatar VARCHAR",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(__import__('sqlalchemy').text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists

    db.close()

# ── Auth Routes ──────────────────────────────────────────────────────────────
class RegisterReq(BaseModel):
    username: str
    email:    str
    password: str

class LoginReq(BaseModel):
    username: str
    password: str

@app.post("/register")
def register(req: RegisterReq, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(400, "Username already taken")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_pw(req.password),
        token=gen_token(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": user.token, "username": user.username, "id": user.id}

@app.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or user.password_hash != hash_pw(req.password):
        raise HTTPException(400, "Invalid username or password")
    return {"token": user.token, "username": user.username, "id": user.id}

@app.get("/me")
def me(token: str, db: Session = Depends(get_db)):
    user = require_user(token, db)
    return serialize_user(user, user.id, db)

# ── Category Routes ──────────────────────────────────────────────────────────
@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "icon": c.icon} for c in db.query(Category).all()]

# ── Post Routes ──────────────────────────────────────────────────────────────
@app.post("/posts")
async def create_post(
    token:          str              = Form(...),
    title:          str              = Form(...),
    description:    str              = Form(...),
    address_street: str              = Form(""),
    address_city:   str              = Form(""),
    address_state:  str              = Form(""),
    location_zip:   str              = Form(...),
    location_name:  str              = Form(...),
    tags:           str              = Form(""),
    category_ids:   str              = Form(""),
    manual_lat:     Optional[float]  = Form(None),
    manual_lng:     Optional[float]  = Form(None),
    photos:         List[UploadFile] = File([]),
    db:             Session          = Depends(get_db),
):
    user = require_user(token, db)

    saved = []
    for photo in photos:
        if photo.filename:
            ext = Path(photo.filename).suffix or ".jpg"
            fname = f"{uuid.uuid4().hex}{ext}"
            url = upload_file(photo.file.read(), fname)
            saved.append(url)

    # Use manual coordinates if provided, otherwise geocode the address
    if manual_lat is not None and manual_lng is not None:
        lat, lng = manual_lat, manual_lng
    else:
        addr_parts = [address_street, address_city, address_state, location_zip]
        addr_str = ", ".join(p for p in addr_parts if p)
        lat, lng = geocode(addr_str)

    post = Post(
        user_id=user.id,
        title=title,
        description=description,
        address_street=address_street,
        address_city=address_city,
        address_state=address_state,
        location_zip=location_zip,
        location_name=location_name,
        lat=lat,
        lng=lng,
        photos=json.dumps(saved),
    )

    for raw in [t.strip().lstrip("#") for t in tags.split(",") if t.strip()]:
        tag = db.query(Tag).filter(Tag.name == raw).first()
        if not tag:
            tag = Tag(name=raw)
            db.add(tag)
        post.tags.append(tag)

    for raw_id in [c.strip() for c in category_ids.split(",") if c.strip()]:
        cat = db.query(Category).filter(Category.id == int(raw_id)).first()
        if cat:
            post.categories.append(cat)

    db.add(post)
    db.commit()
    db.refresh(post)
    return serialize_post(post, user.id)

@app.patch("/posts/{post_id}")
async def edit_post(
    post_id:     int,
    token:       str              = Form(...),
    title:       Optional[str]    = Form(None),
    description: Optional[str]    = Form(None),
    tags:        Optional[str]    = Form(None),
    category_ids:Optional[str]    = Form(None),
    remove_photos: Optional[str]  = Form(None),   # JSON array of filenames to remove
    photos:      List[UploadFile] = File([]),
    db:          Session          = Depends(get_db),
):
    user = require_user(token, db)
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    if post.user_id != user.id:
        raise HTTPException(403, "Not your post")

    if title is not None:
        post.title = title
    if description is not None:
        post.description = description

    # Handle photo removals
    existing = json.loads(post.photos or "[]")
    if remove_photos:
        to_remove = set(json.loads(remove_photos))
        for f in to_remove:
            fname = f.split("/")[-1]
            delete_file(fname)
        existing = [f for f in existing if f.split("/")[-1] not in to_remove and f not in to_remove]

    # Append new photos
    for photo in photos:
        if photo.filename:
            ext = Path(photo.filename).suffix or ".jpg"
            fname = f"{uuid.uuid4().hex}{ext}"
            url = upload_file(photo.file.read(), fname)
            existing.append(url)

    post.photos = json.dumps(existing)

    # Update tags if provided
    if tags is not None:
        post.tags.clear()
        for raw in [t.strip().lstrip("#") for t in tags.split(",") if t.strip()]:
            tag = db.query(Tag).filter(Tag.name == raw).first()
            if not tag:
                tag = Tag(name=raw)
                db.add(tag)
            post.tags.append(tag)

    # Update categories if provided
    if category_ids is not None:
        post.categories.clear()
        for raw_id in [c.strip() for c in category_ids.split(",") if c.strip()]:
            cat = db.query(Category).filter(Category.id == int(raw_id)).first()
            if cat:
                post.categories.append(cat)

    db.commit()
    db.refresh(post)
    return serialize_post(post, user.id)

@app.delete("/posts/{post_id}")
def delete_post(post_id: int, token: str, db: Session = Depends(get_db)):
    user = require_user(token, db)
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    if post.user_id != user.id:
        raise HTTPException(403, "Not your post")
    db.delete(post)
    db.commit()
    return {"deleted": True}

@app.get("/feed")
def feed(
    category_id: Optional[int] = None,
    zip_code:    Optional[str] = None,
    following:   bool          = False,
    tag:         Optional[str] = None,
    token:       Optional[str] = None,
    db:          Session       = Depends(get_db),
):
    uid = None
    if token:
        u = db.query(User).filter(User.token == token).first()
        if u:
            uid = u.id

    q = db.query(Post)

    if following and uid:
        followed_ids = [f.following_id for f in db.query(Follow).filter(Follow.follower_id == uid).all()]
        q = q.filter(Post.user_id.in_(followed_ids))
    if category_id:
        q = q.filter(Post.categories.any(Category.id == category_id))
    if zip_code:
        q = q.filter(Post.location_zip == zip_code)
    if tag:
        q = q.filter(Post.tags.any(Tag.name == tag))

    posts = q.order_by(Post.created_at.desc()).limit(60).all()
    return [serialize_post(p, uid) for p in posts]

@app.get("/trending")
def trending(token: Optional[str] = None, db: Session = Depends(get_db)):
    uid = None
    if token:
        u = db.query(User).filter(User.token == token).first()
        if u:
            uid = u.id
    cutoff = datetime.utcnow() - timedelta(days=7)
    posts = db.query(Post).filter(Post.created_at >= cutoff).all()
    posts_sorted = sorted(posts, key=lambda p: len(p.likes), reverse=True)[:5]
    return [serialize_post(p, uid) for p in posts_sorted]

@app.get("/search")
def search(q: str = "", token: Optional[str] = None, db: Session = Depends(get_db)):
    uid = None
    if token:
        u = db.query(User).filter(User.token == token).first()
        if u:
            uid = u.id

    if not q:
        return {"users": [], "posts": []}

    pattern = f"%{q}%"

    users = db.query(User).filter(User.username.ilike(pattern)).limit(10).all()
    user_results = []
    for user in users:
        user_results.append({
            "id":         user.id,
            "username":   user.username,
            "bio":        user.bio or "",
            "avatar":     user.avatar,
            "post_count": len(user.posts),
        })

    posts = db.query(Post).filter(
        Post.title.ilike(pattern) |
        Post.location_name.ilike(pattern) |
        Post.description.ilike(pattern)
    ).limit(20).all()
    post_results = [serialize_post(p, uid) for p in posts]

    return {"users": user_results, "posts": post_results}

@app.get("/posts/{post_id}")
def get_post(post_id: int, token: Optional[str] = None, db: Session = Depends(get_db)):
    uid = None
    if token:
        u = db.query(User).filter(User.token == token).first()
        if u:
            uid = u.id
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    return serialize_post(post, uid)

@app.post("/posts/{post_id}/like")
def toggle_like(post_id: int, token: str, db: Session = Depends(get_db)):
    user = require_user(token, db)
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    existing = db.query(Like).filter(Like.user_id == user.id, Like.post_id == post_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"liked": False, "likes": len(post.likes) - 1}
    db.add(Like(user_id=user.id, post_id=post_id))
    notify(db, post.user_id, user.id, "like", post_id)
    db.commit()
    db.refresh(post)
    return {"liked": True, "likes": len(post.likes)}

# ── Comment Routes ────────────────────────────────────────────────────────────
def serialize_comment(comment: Comment):
    return {
        "id":      comment.id,
        "content": comment.content,
        "author":  {
            "id":       comment.author.id,
            "username": comment.author.username,
            "avatar":   comment.author.avatar if (comment.author.avatar and comment.author.avatar.startswith("http")) else (f"/uploads/{comment.author.avatar}" if comment.author.avatar else None),
        },
        "created_at": comment.created_at.isoformat(),
    }

@app.get("/posts/{post_id}/comments")
def get_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    return [serialize_comment(c) for c in post.comments]

@app.post("/posts/{post_id}/comments")
def add_comment(post_id: int, token: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(token, db)
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    if not content.strip():
        raise HTTPException(400, "Comment cannot be empty")
    comment = Comment(user_id=user.id, post_id=post_id, content=content.strip())
    db.add(comment)
    notify(db, post.user_id, user.id, "comment", post_id)
    db.commit()
    db.refresh(comment)
    return serialize_comment(comment)

@app.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, token: str, db: Session = Depends(get_db)):
    user = require_user(token, db)
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(404, "Comment not found")
    if comment.user_id != user.id:
        raise HTTPException(403, "Not your comment")
    db.delete(comment)
    db.commit()
    return {"deleted": True}

# ── Follow Routes ─────────────────────────────────────────────────────────────
@app.post("/users/{user_id}/follow")
def toggle_follow(user_id: int, token: str, db: Session = Depends(get_db)):
    me = require_user(token, db)
    if me.id == user_id:
        raise HTTPException(400, "You cannot follow yourself")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    existing = db.query(Follow).filter(Follow.follower_id == me.id, Follow.following_id == user_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        db.refresh(target)
        return {"following": False, "follower_count": len(target.followers)}
    db.add(Follow(follower_id=me.id, following_id=user_id))
    notify(db, user_id, me.id, "follow")
    db.commit()
    db.refresh(target)
    return {"following": True, "follower_count": len(target.followers)}

# ── Notification Routes ───────────────────────────────────────────────────────
@app.get("/notifications")
def get_notifications(token: str, db: Session = Depends(get_db)):
    user = require_user(token, db)
    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    result = []
    for n in notifs:
        actor = db.query(User).filter(User.id == n.actor_id).first()
        result.append({
            "id":         n.id,
            "type":       n.type,
            "read":       n.read,
            "actor":      {"id": actor.id, "username": actor.username} if actor else None,
            "post_id":    n.post_id,
            "created_at": n.created_at.isoformat(),
        })
    return result

@app.get("/notifications/unread-count")
def unread_count(token: str, db: Session = Depends(get_db)):
    user = require_user(token, db)
    count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.read == False,
    ).count()
    return {"count": count}

@app.post("/notifications/mark-read")
def mark_notifications_read(token: str, db: Session = Depends(get_db)):
    user = require_user(token, db)
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.read == False,
    ).update({"read": True})
    db.commit()
    return {"ok": True}

# ── User Profile Routes ───────────────────────────────────────────────────────
@app.get("/users/{user_id}")
def get_user(user_id: int, token: Optional[str] = None, db: Session = Depends(get_db)):
    uid = None
    if token:
        u = db.query(User).filter(User.token == token).first()
        if u:
            uid = u.id
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return serialize_user(user, uid, db)

@app.get("/users/{user_id}/posts")
def user_posts(user_id: int, token: Optional[str] = None, db: Session = Depends(get_db)):
    uid = None
    if token:
        u = db.query(User).filter(User.token == token).first()
        if u:
            uid = u.id
    posts = db.query(Post).filter(Post.user_id == user_id).order_by(Post.created_at.desc()).all()
    return [serialize_post(p, uid) for p in posts]

@app.patch("/users/me")
def edit_profile(
    token:    str           = Form(...),
    bio:      Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    db:       Session       = Depends(get_db),
):
    user = require_user(token, db)
    if username and username != user.username:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(400, "Username already taken")
        user.username = username
    if bio is not None:
        user.bio = bio
    db.commit()
    db.refresh(user)
    return serialize_user(user, user.id, db)

@app.delete("/users/me")
def delete_account(token: str, db: Session = Depends(get_db)):
    user = require_user(token, db)
    # Delete all posts and their photos
    posts = db.query(Post).filter(Post.user_id == user.id).all()
    for post in posts:
        for f in json.loads(post.photos or "[]"):
            delete_file(f.split("/")[-1])
        db.delete(post)
    # Delete avatar file
    if user.avatar:
        delete_file(user.avatar.split("/")[-1])
    # Delete associated records
    db.query(Like).filter(Like.user_id == user.id).delete()
    db.query(Follow).filter((Follow.follower_id == user.id) | (Follow.following_id == user.id)).delete()
    db.query(Comment).filter(Comment.user_id == user.id).delete()
    db.query(Notification).filter((Notification.user_id == user.id) | (Notification.actor_id == user.id)).delete()
    db.delete(user)
    db.commit()
    return {"deleted": True}

@app.post("/users/me/avatar")
async def upload_avatar(
    token:  str        = Form(...),
    avatar: UploadFile = File(...),
    db:     Session    = Depends(get_db),
):
    user = require_user(token, db)
    ext = Path(avatar.filename).suffix or ".jpg"
    fname = f"avatar_{uuid.uuid4().hex}{ext}"
    url = upload_file(avatar.file.read(), fname)
    user.avatar = url
    db.commit()
    return {"avatar": url}
