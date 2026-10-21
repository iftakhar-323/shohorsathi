"""Download high-quality imagery for ShohorSathi presentation & production UI.
Uses curated Unsplash high-resolution photography.
"""
import os
import urllib.request

ASSETS = {
    # Service categories
    "apps/customer-web/public/images/categories/ac-repair.jpg": 
        "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?w=600&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/categories/electrical.jpg":
        "https://images.unsplash.com/photo-1621905252507-b35492cc74b4?w=600&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/categories/plumbing.jpg":
        "https://images.unsplash.com/photo-1585704032915-c3400ca199e7?w=600&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/categories/cleaning.jpg":
        "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=600&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/categories/appliances.jpg":
        "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=600&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/categories/painting.jpg":
        "https://images.unsplash.com/photo-1589939705384-5185137a7f0f?w=600&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/categories/pest-control.jpg":
        "https://images.unsplash.com/photo-1607400201515-c2c41c07d307?w=600&auto=format&fit=crop&q=80",

    # Hero and Seasonal Campaigns
    "apps/customer-web/public/images/banners/hero-service.jpg":
        "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=1200&auto=format&fit=crop&q=85",
    "apps/customer-web/public/images/banners/eid-cleaning.jpg":
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=900&auto=format&fit=crop&q=85",
    "apps/customer-web/public/images/banners/monsoon-waterproofing.jpg":
        "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?w=900&auto=format&fit=crop&q=85",
    "apps/customer-web/public/images/banners/summer-ac.jpg":
        "https://images.unsplash.com/photo-1590486803833-1c5dc8ddd4c8?w=900&auto=format&fit=crop&q=85",

    # AI Quote Sample Issues for 1-Click university presentation demo
    "apps/customer-web/public/images/ai-samples/ac-leak.jpg":
        "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?w=800&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/ai-samples/pipe-leak.jpg":
        "https://images.unsplash.com/photo-1585704032915-c3400ca199e7?w=800&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/ai-samples/burnt-socket.jpg":
        "https://images.unsplash.com/photo-1555664424-778a1e5e1b48?w=800&auto=format&fit=crop&q=80",
    "apps/customer-web/public/images/ai-samples/wall-damp.jpg":
        "https://images.unsplash.com/photo-1598928506311-c55ded91a20c?w=800&auto=format&fit=crop&q=80",
}

def main():
    for rel_path, url in ASSETS.items():
        dest = os.path.abspath(rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            print(f"Already exists: {rel_path} ({os.path.getsize(dest)} bytes)")
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read()
                with open(dest, "wb") as f:
                    f.write(data)
                print(f"Downloaded: {rel_path} ({len(data)} bytes)")
        except Exception as e:
            print(f"Failed {rel_path}: {e}")

if __name__ == "__main__":
    main()
