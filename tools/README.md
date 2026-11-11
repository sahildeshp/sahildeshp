# Profile README generator

`gen.py` writes `README.md` and the SVG tiles in `assets/` (a light and a dark version of each).

Edit the content in `gen.py` (headline, roles, projects, skills), then run from the repository root:

```
pip install fonttools brotli
python3 tools/gen.py .
```

The fonts in `fonts/` are static instances of Bricolage Grotesque and Instrument Sans (SIL Open Font License), the same faces as sahildeshp.github.io. Each SVG embeds only the glyphs it uses.
