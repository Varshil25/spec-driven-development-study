This repository already contains `bookmarks`, a command-line bookmark manager that stores bookmarks in SQLite. Read the existing code and any documentation in the repository before changing it. Add the two features below; every existing command must keep working exactly as it does now.

1. **Import.** `python -m bookmarks [--db PATH] import FILE --format csv|json` reads bookmarks from FILE in the same formats that `export` writes: CSV with the header row `id,url,title,tags`, or a JSON array of objects with the keys `url`, `title` and `tags` (a list of strings). Each bookmark in the file is added exactly as the `add` command would add it, with the same rules for URLs, titles and tags. The `id` in the file is ignored, and new ids are assigned as usual. When it finishes it prints `imported N` to standard output, where N is the number of bookmarks added. If FILE cannot be read, or is not valid CSV or JSON of that shape, it prints an error message to standard error, imports nothing, and exits with status 2.

2. **HTML export.** `export --format html` prints all bookmarks, ordered by id, as an HTML page in this form:

```
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Bookmarks</title></head>
<body>
<ul>
<li><a href="URL">TITLE</a> <small>TAGS</small></li>
</ul>
</body>
</html>
```

with one `<li>` line per bookmark, where TAGS are the bookmark's tags joined with commas in alphabetical order.

Examples, with a file `in.json` containing `[{"url": "https://docs.python.org", "title": "Python docs", "tags": ["python", "docs"]}, {"url": "https://example.com", "title": "Example", "tags": []}]` and an empty database (`<TAB>` stands for a tab character):

```
$ python -m bookmarks --db b.db import in.json --format json
imported 2
$ python -m bookmarks --db b.db list
1<TAB>https://docs.python.org<TAB>Python docs<TAB>docs,python
2<TAB>https://example.com<TAB>Example<TAB>
$ python -m bookmarks --db b.db export --format html
(an HTML page that contains <a href="https://docs.python.org">Python docs</a>)
```
