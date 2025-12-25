import os
import imagehash
from PIL import Image
from pathlib import Path

class ImageHashManager:
    def __init__(self, library_path):
        self.library_path = Path(library_path)
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.hashes = {} # path -> hash
        self._load_library_hashes()

    def _load_library_hashes(self):
        """Pre-calculate hashes for all images in the library."""
        for img_path in self.library_path.glob("**/*"):
            if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                try:
                    h = self._compute_hash(img_path)
                    if h:
                        self.hashes[str(img_path)] = h
                except Exception:
                    pass

    def _compute_hash(self, image_path_or_obj):
        try:
            if isinstance(image_path_or_obj, (str, Path)):
                img = Image.open(image_path_or_obj)
            else:
                img = image_path_or_obj
            return imagehash.phash(img)
        except Exception:
            return None

    def is_similar(self, new_image_path_or_object, threshold=5):
        """
        Checks if the image is similar to anything in the library.
        Returns (bool, matching_path)
        """
        new_hash = self._compute_hash(new_image_path_or_object)
        if not new_hash:
            return False, None
            
        for path, h in self.hashes.items():
            if new_hash - h <= threshold: # Hamming distance
                return True, path
        return False, None

    def add_to_library(self, image_path):
        """Adds a new image to the library and memory."""
        h = self._compute_hash(image_path)
        if h:
            self.hashes[str(image_path)] = h
