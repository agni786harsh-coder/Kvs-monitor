import os
from pathlib import Path

import requests


URL = (
    "https://examinationservices.nic.in/recsys2025/root/"
    "CandidateLogin.aspx?enc=Ei4cajBkK1gZSfgr53ImFbEsl0hvvhEEwgxfU0IzC28jtU4y"
    "hpqb3pomlo4g+VC8"
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

STATE_FILE = Path("maintenance_state.txt")

MAINTENANCE_STATE = "maintenance"
AVAILABLE_STATE = "available"


def check_website():
    """
    Returns:
        True: maintenance detected
        False: maintenance not detected
        None: request failed or returned an unusable response
    """

    try:
        response = requests.get(
            URL,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 KVS-NVS-Monitor/1.0"
            },
        )

        page = response.text.lower()

        # Check the actual page content before interpreting
        # the HTTP status code. Many sites serve their maintenance
        # page with a non-2xx status (e.g. 503), so the content
        # check must come first or a real maintenance window would
        # be misread as "request failed".
        if "under maintenance" in page:
            return True

        # A normal successful response without the maintenance
        # message means the page is available.
        if 200 <= response.status_code < 300:
            return False

        # Do not interpret an error page as "available".
        print(
            f"Unusable HTTP status: {response.status_code}. "
            "Previous state will be preserved."
        )
        return None

    except requests.RequestException as error:
        print(f"Website request failed: {error}")
        return None


def read_saved_state():
    if not STATE_FILE.exists():
        return None

    state = STATE_FILE.read_text(
        encoding="utf-8"
    ).strip()

    if state in (
        MAINTENANCE_STATE,
        AVAILABLE_STATE,
    ):
        return state

    return None


def save_state(state):
    STATE_FILE.write_text(
        state,
        encoding="utf-8",
    )


def send_telegram(message):
    telegram_url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        telegram_url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
        },
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API returned an error: {result}"
        )


def main():
    current_result = check_website()
    previous_state = read_saved_state()

    print(f"Previous saved state: {previous_state}")
    print(f"Current website result: {current_result}")

    # If the request failed, preserve the previous state.
    # Do not send an alert and do not overwrite the state.
    if current_result is None:
        print("Request failed. Previous state preserved.")
        return

    current_state = (
        MAINTENANCE_STATE
        if current_result
        else AVAILABLE_STATE
    )

    # First run establishes the baseline.
    # It deliberately sends no notification.
    if previous_state is None:
        save_state(current_state)

        print(
            f"Initial state saved as {current_state}. "
            "No notification sent."
        )

        return

    # No change means no notification.
    if current_state == previous_state:
        print("No state change. No Telegram message sent.")
        return

    # Available -> maintenance
    if (
        previous_state == AVAILABLE_STATE
        and current_state == MAINTENANCE_STATE
    ):
        send_telegram(
            "🔴 KVS/NVS Candidate Login Alert\n\n"
            'The candidate login page is now showing '
            '"Under Maintenance".'
        )

    # Maintenance -> available
    elif (
        previous_state == MAINTENANCE_STATE
        and current_state == AVAILABLE_STATE
    ):
        send_telegram(
            "🟢 KVS/NVS Candidate Login Alert\n\n"
            "Maintenance has ended. "
            "The candidate login page is available again."
        )

    # Save only after the notification succeeds.
    save_state(current_state)

    print(
        f"State changed from {previous_state} "
        f"to {current_state}."
    )


if __name__ == "__main__":
    main()
