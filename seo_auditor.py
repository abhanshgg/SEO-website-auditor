"""SEO Website Auditor - checks a web page for common SEO problems and gives a score."""
import argparse
import json
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (SEO-Auditor-Project)"}


def fetch(url, timeout=10):
    """Download a page. Returns (response, load_time_in_seconds)."""
    start = time.time()
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    return response, round(time.time() - start, 2)


def url_exists(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=8).status_code == 200
    except requests.RequestException:
        return False


def check(name, passed, message, points):
    return {"name": name, "passed": passed, "message": message, "points": points}


def audit_html(html, url, load_time=0.0, https_ok=True):
    """Run all on-page checks on HTML text and return a list of results."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # 1. Title tag (ideal: 30-60 characters)
    title = soup.title.get_text(strip=True) if soup.title else ""
    ok = 30 <= len(title) <= 60
    results.append(check("Title tag", ok,
        f"Title is {len(title)} chars (ideal 30-60): '{title}'" if title else "Missing <title> tag", 15))

    # 2. Meta description (ideal: 70-160 characters)
    tag = soup.find("meta", attrs={"name": "description"})
    desc = tag.get("content", "").strip() if tag else ""
    ok = 70 <= len(desc) <= 160
    results.append(check("Meta description", ok,
        f"Description is {len(desc)} chars (ideal 70-160)" if desc else "Missing meta description", 15))

    # 3. Exactly one H1
    h1s = soup.find_all("h1")
    results.append(check("H1 heading", len(h1s) == 1,
        f"Found {len(h1s)} H1 tags (should be exactly 1)", 10))

    # 4. Image alt text
    images = soup.find_all("img")
    missing = [i.get("src", "?") for i in images if not i.get("alt", "").strip()]
    results.append(check("Image alt text", not missing,
        "All images have alt text" if not missing else f"{len(missing)} of {len(images)} images missing alt text", 10))

    # 5. Canonical link
    canonical = soup.find("link", rel="canonical")
    results.append(check("Canonical tag", canonical is not None,
        "Canonical tag present" if canonical else "No canonical tag (can cause duplicate-content issues)", 5))

    # 6. noindex check - the kind of issue that hides a site from Google
    robots = soup.find("meta", attrs={"name": "robots"})
    noindex = bool(robots and "noindex" in robots.get("content", "").lower())
    results.append(check("Indexable (no 'noindex')", not noindex,
        "Page tells Google NOT to index it!" if noindex else "Page can be indexed", 15))

    # 7. Viewport (mobile friendly)
    viewport = soup.find("meta", attrs={"name": "viewport"})
    results.append(check("Mobile viewport", viewport is not None,
        "Viewport tag present" if viewport else "Missing viewport tag (bad for mobile)", 5))

    # 8. HTTPS
    results.append(check("HTTPS", https_ok and url.startswith("https"),
        "Site uses HTTPS" if url.startswith("https") else "Site is not using HTTPS", 10))

    # 9. Load time
    results.append(check("Load time", load_time < 2.0,
        f"Page loaded in {load_time}s (aim for under 2s)", 10))

    # 10. Word count (thin content)
    words = len(soup.get_text(" ", strip=True).split())
    results.append(check("Content length", words >= 300,
        f"About {words} words (300+ recommended)", 5))
    return results


def audit_site_files(url):
    """Check robots.txt and sitemap.xml at the site root."""
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    results = []
    for name in ("robots.txt", "sitemap.xml"):
        found = url_exists(urljoin(base, "/" + name))
        results.append(check(name, found, f"{name} found" if found else f"{name} not found", 0))
    return results


def calculate_score(results):
    total = sum(r["points"] for r in results)
    earned = sum(r["points"] for r in results if r["passed"])
    return round(earned / total * 100) if total else 0


def print_report(url, results, score):
    print(f"\nSEO AUDIT REPORT for {url}\n" + "=" * 60)
    for r in results:
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['name']}: {r['message']}")
    print("=" * 60 + f"\nSEO SCORE: {score}/100\n")


def main():
    parser = argparse.ArgumentParser(description="Simple SEO auditor")
    parser.add_argument("url", help="Page to audit, e.g. https://example.com")
    parser.add_argument("--json", help="Save report to this JSON file")
    args = parser.parse_args()

    url = args.url if args.url.startswith("http") else "https://" + args.url
    try:
        response, load_time = fetch(url)
        response.raise_for_status()
    except requests.RequestException as error:
        raise SystemExit(f"Could not fetch {url}: {error}")

    results = audit_html(response.text, response.url, load_time)
    results += audit_site_files(response.url)
    score = calculate_score(results)
    print_report(response.url, results, score)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"url": response.url, "score": score, "checks": results}, f, indent=2)
        print(f"Report saved to {args.json}")


if __name__ == "__main__":
    main()
