from abc import ABC, abstractmethod

class BaseScraper(ABC):
    @abstractmethod
    def get_product_images(self, product_code: str) -> list[str]:
        """
        Fetches image URLs for the given product code.
        Returns a list of image URLs.
        """
        pass
