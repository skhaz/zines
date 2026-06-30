build:
	uv run tools/build_site.py
	uvx --from 'pagefind[bin]' python -m pagefind --site . --output-subdir pagefind

clean:
	find english portuguese -name index.html -delete
	find english portuguese -name '*.html' ! -name index.html -delete
	rm -rf pagefind sitemap.xml feed.xml random.json

.PHONY: build clean
