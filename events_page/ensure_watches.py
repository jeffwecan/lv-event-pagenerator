#!/usr/bin/env python
import logging
import os

import logzero
from googleapiclient.errors import HttpError
from logzero import logger

from google_apis import calendar, drive
from webhook import get_webhook_token

# DEFAULT_EXPIRATION_IN_DAYS = 1
DEFAULT_EXPIRATION_IN_DAYS = 0.1
DEFAULT_CALENDAR_ID = "information@losverdesatx.org"
DEFAULT_WEB_HOOK_ADDRESS = (
    "https://us-central1-losverdesatx-events.cloudfunctions.net/push-webhook-receiver"
)


logzero.loglevel(logging.INFO)


def ensure_watches(web_hook_address, webhook_token, calendar_id, settings_file_id):
    ensure_events_watch(
        web_hook_address=web_hook_address,
        webhook_token=webhook_token,
        calendar_id=calendar_id,
    )
    ensure_drive_watch(
        web_hook_address=web_hook_address,
        webhook_token=webhook_token,
        settings_file_id=settings_file_id,
    )


def ensure_watch(
    api_module,
    channel_id,
    web_hook_address,
    webhook_token,
    watch_kwargs=None,
    expiration_in_days=DEFAULT_EXPIRATION_IN_DAYS,
):
    if watch_kwargs is None:
        watch_kwargs = dict()

    service = getattr(api_module, "build_service")()
    try:
        response = getattr(api_module, "ensure_watch")(
            service=service,
            channel_id=channel_id,
            web_hook_address=web_hook_address,
            webhook_token=webhook_token,
            expiration_in_days=expiration_in_days,
            **watch_kwargs,
        )
        logger.debug(f"ensure_watch(): {response=}")
    except HttpError as err:
        logger.debug(err)
        if err.reason != f"Channel id {channel_id} not unique":
            # already have watch in place
            logger.exception(f"unexpected err: {err}")
            raise err
        logger.warning(
            f"Watch {channel_id} already present ({err=}). Happily continuing..."
        )


def ensure_events_watch(web_hook_address, webhook_token, calendar_id):
    ensure_watch(
        api_module=calendar,
        channel_id=f"events-page-{calendar_id.split('@', 1)[0]}-watch",
        web_hook_address=web_hook_address,
        webhook_token=webhook_token,
        watch_kwargs=dict(
            calendar_id=calendar_id,
        ),
    )


def ensure_drive_watch(web_hook_address, webhook_token, settings_file_id):
    ensure_watch(
        api_module=drive,
        channel_id=f"events-page-{settings_file_id}-watch",
        web_hook_address=web_hook_address,
        webhook_token=webhook_token,
        watch_kwargs=dict(
            file_id=settings_file_id,
        ),
    )


if __name__ == "__main__":
    import argparse
    import logging

    import logzero

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-q",
        "--quiet",
        help="modify output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "-c",
        "--calendar-id",
        default=os.getenv("EVENTS_PAGE_CALENDAR_ID", DEFAULT_CALENDAR_ID),
    )
    parser.add_argument(
        "-s",
        "--settings-file-name",
        default=drive.DEFAULT_SETTINGS_FILE_NAME,
    )
    parser.add_argument(
        "-g",
        "--gdrive-folder-name",
        default=drive.DEFAULT_FOLDER_NAME,
    )
    parser.add_argument(
        "-w",
        "--web-hook-address",
        default=DEFAULT_WEB_HOOK_ADDRESS,
    )
    args = parser.parse_args()

    if args.quiet:
        logzero.loglevel(logging.INFO)

    settings_file_id = drive.get_settings_file_id(
        service=drive.build_service(),
        folder_name=args.gdrive_folder_name,
        file_name=args.settings_file_name,
    )
    ensure_watches(
        web_hook_address=args.web_hook_address,
        webhook_token=get_webhook_token(),
        calendar_id=args.calendar_id,
        settings_file_id=settings_file_id,
    )
