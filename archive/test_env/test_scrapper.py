import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    # Initialize the open-source crawler
    async with AsyncWebCrawler(verbose=True) as crawler:
        # We will test it against a standard link
        result = await crawler.arun(url="https://wikipedia.org")
        
        print("\n--- Clean Markdown Extracted ---")
        # Crawl4AI automatically strips HTML boilerplate and outputs markdown
        print(result.markdown[:1000]) # Printing the first 1000 characters

if __name__ == "__main__":
    asyncio.run(main())
