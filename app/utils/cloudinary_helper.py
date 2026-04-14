import cloudinary
import cloudinary.uploader
import cloudinary.api
import os

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def upload_image(file_obj, folder="products"):
    """
    Uploads file to Cloudinary and returns the URL
    """
    result = cloudinary.uploader.upload(
        file_obj,
        folder=folder
    )
    return result.get("secure_url")