# Manual interface check

After launch, check 1440×900, 1024×768 and 390×844:

1. Home: navigation, a list of 19 scripts and an editor are visible. There is a menu on the phone
   it opens with a button; horizontal scrolling of the page is not necessary.
2. "With error" → launch: REJECTED, no data recorded, JSON contains details.
3. Cache hit/miss: the second step is 0 SQL. Switching Result/Python/JSON works.
4. "Run all": the buttons are blocked; missing services are clearly skipped.
5. Export saves the JSON of the current launches, copying works on localhost/HTTPS.
6. Catalog: SVG cards, search, creation, price editing, negative price,
   deleting a test product. Esc closes the dialog, but Tab does not exit it.
7. Open a private window: the recordings of the previous session are not visible.
8. Schemas: Product/Category/Tag/Report switch fields and JSON.
9. Integration: real health-check, status unavailable/not configured.
10. Admin requires login. The API Explorer opens the generated schema.

Accessibility: skip-link, label for input, aria-live for notifications,
visible focus, native dialog, preferences-reduced-motion support.


## RU / EN

- On the desktop and mobile screen, the RU/EN switch is visible in the upper panel.
- The active language is highlighted; both buttons are accessible from the keyboard and have an aria label.
- Switching returns to the current page and the selected script.
- The selected language is saved after updating and switching between sections.
- English long titles and captions are not cut off on a narrow screen.
- Lab, search, filters, statuses, forms and messages change the language;
  The product names and saved data remain the same.