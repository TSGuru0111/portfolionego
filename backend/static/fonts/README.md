# Local fonts (WeasyPrint)

WeasyPrint cannot reliably load fonts via Google CDN, so the three
font files below must be downloaded manually and placed in this folder
before the PDF exporter will render correctly.

| File                          | Source                                                          |
|-------------------------------|-----------------------------------------------------------------|
| `Inter-Regular.ttf`           | https://fonts.google.com/specimen/Inter                         |
| `Inter-Bold.ttf`              | https://fonts.google.com/specimen/Inter                         |
| `PlayfairDisplay-Bold.ttf`    | https://fonts.google.com/specimen/Playfair+Display              |

These files are git-ignored by design — do not commit them.
