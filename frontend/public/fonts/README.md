# Local web fonts

Place the following `.woff2` files here so Tailwind's font stack
resolves locally (Google Fonts CDN is unreliable for WeasyPrint and
inconsistent in some Indian network environments):

- `Inter-Regular.woff2`
- `Inter-Bold.woff2`
- `PlayfairDisplay-Bold.woff2`

The matching @font-face declarations live in `src/index.css`.
