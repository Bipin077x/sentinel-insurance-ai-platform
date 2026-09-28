import os
import random
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image, ImageDraw, ImageFilter

DIR = os.path.dirname(os.path.abspath(__file__))

def generate_native_pdf():
    path = os.path.join(DIR, "native_claim.pdf")
    c = canvas.Canvas(path, pagesize=letter)
    c.drawString(100, 750, "Claim Form")
    c.drawString(100, 730, "Policy ID: POL-12345")
    c.drawString(100, 710, "Claim Type: Medical")
    c.drawString(100, 690, "Amount: $1250.00")
    c.save()
    print(f"Generated {path}")

def generate_scanned_png():
    path = os.path.join(DIR, "scanned_claim.png")
    img = Image.new('RGB', (800, 600), color='white')
    d = ImageDraw.Draw(img)
    d.text((50, 50), "Claim Form", fill='black')
    d.text((50, 100), "Policy ID: POL-67890", fill='black')
    d.text((50, 150), "Claim Type: Property", fill='black')
    d.text((50, 200), "Amount: $5000.00", fill='black')
    img.save(path)
    print(f"Generated {path}")

def generate_garbled_scan():
    path = os.path.join(DIR, "garbled_scan.png")
    img = Image.new('RGB', (800, 600), color='white')
    d = ImageDraw.Draw(img)
    d.text((50, 50), "Claim Form", fill='black')
    d.text((50, 100), "Policy ID: POL-UNKNOWN", fill='black')
    d.text((50, 150), "Amount: $???", fill='black')
    
    for _ in range(50000):
        x = random.randint(0, 799)
        y = random.randint(0, 599)
        img.putpixel((x, y), (0, 0, 0))
    
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    img.save(path)
    print(f"Generated {path}")

if __name__ == "__main__":
    generate_native_pdf()
    generate_scanned_png()
    generate_garbled_scan()
