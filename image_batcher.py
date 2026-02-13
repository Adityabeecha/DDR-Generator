"""
Image batching utilities for efficient PDF to image processing.
"""
import fitz
from PIL import Image
from typing import List, Dict
import io


def pdf_to_images(pdf_file, max_pages: int = None) -> List[Image.Image]:
    """
    Convert PDF pages to PIL Image objects with compression.
    
    Args:
        pdf_file: Uploaded PDF file object
        max_pages: Maximum number of pages to convert (None = all)
        
    Returns:
        List of compressed PIL Image objects
    """
    # Reset file pointer to beginning
    pdf_file.seek(0)
    
    pdf_bytes = pdf_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    images = []
    page_count = min(doc.page_count, max_pages) if max_pages else doc.page_count
    
    try:
        for page_num in range(page_count):
            page = doc[page_num]
            
            # Render at 150 DPI (optimized for quota efficiency)
            mat = fitz.Matrix(2.08, 2.08)  # 150/72 = 2.08
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Compress image to reduce payload size
            # Convert to RGB if needed (for JPEG compression)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Compress using JPEG with quality=85
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            buffer.seek(0)
            compressed_img = Image.open(buffer)
            
            images.append(compressed_img)
    finally:
        doc.close()
    
    return images


def create_image_batches(
    pdf_file, 
    images_per_batch: int = 10,
    max_total_pages: int = None
) -> List[Dict]:
    """
    Convert PDF to images and batch them for API calls.
    
    Args:
        pdf_file: Uploaded PDF file object
        images_per_batch: Number of images per batch
        max_total_pages: Maximum total pages to process
        
    Returns:
        List of batch dictionaries with images and metadata
    """
    images = pdf_to_images(pdf_file, max_pages=max_total_pages)
    
    batches = []
    for i in range(0, len(images), images_per_batch):
        batch_images = images[i:i + images_per_batch]
        batch = {
            "images": batch_images,
            "page_range": f"{i+1}-{i+len(batch_images)}",
            "start_page": i + 1,
            "end_page": i + len(batch_images),
            "image_count": len(batch_images)
        }
        batches.append(batch)
    
    return batches


def estimate_batch_count(total_pages: int, images_per_batch: int = 10) -> int:
    """
    Estimate number of API calls needed for image processing.
    
    Args:
        total_pages: Total number of PDF pages
        images_per_batch: Images per batch
        
    Returns:
        Number of batches/API calls needed
    """
    return (total_pages + images_per_batch - 1) // images_per_batch
