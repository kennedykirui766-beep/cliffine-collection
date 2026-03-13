import re
from app.models import Category

def generate_unique_slug(name):
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')

    existing = Category.query.filter_by(slug=slug).first()

    if not existing:
        return slug

    counter = 2
    while True:
        new_slug = f"{slug}-{counter}"
        if not Category.query.filter_by(slug=new_slug).first():
            return new_slug
        counter += 1