import base64
import json
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "streak_state_b64.txt"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()
        page.goto("https://www.streak.tech/")

        print("\n=== STREAK SESSION CAPTURE ===")
        print("1. Log in to Streak (with Kite/broker 2FA) in the browser window.")
        print("2. Open your 3-cap scanner page and confirm it loads properly.")
        input("3. Press ENTER here once logged in to export your session... ")

        state_dict = context.storage_state()
        b64_state = base64.b64encode(json.dumps(state_dict).encode("utf-8")).decode("utf-8")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(b64_state)

        print(f"\nSaved Base64 session to {OUTPUT_FILE}!")
        print("Next steps:")
        print("  1. Copy the entire contents of streak_state_b64.txt")
        print("  2. Paste it into GitHub -> Settings -> Secrets -> Actions -> STREAK_STORAGE_STATE_B64")
        print("  3. Delete streak_state_b64.txt from your local folder (never commit it).")
        browser.close()


if __name__ == "__main__":
    main()
