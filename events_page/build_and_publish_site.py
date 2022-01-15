#!/usr/bin/env python

from time import sleep

import requests
from CloudFlare import CloudFlare
from flask_frozen import Freezer
from logzero import logger

from app import create_app
from config import cfg
from google_apis import storage
from google_apis.secrets import get_cloudflare_api_token


def freeze_site(app):
    freeze_result = Freezer(app).freeze()
    logger.debug(f"{freeze_result=}")
    return freeze_result


def purge_cache(cf, cloudflare_zone):
    logger.debug(f"Loading zone info for {cloudflare_zone=}")
    zones = cf.zones.get(params={"per_page": 50, "name": cloudflare_zone})
    if not zones:
        raise Exception(
            f"Unable to find DNS zone ID for {cloudflare_zone=} at Cloudflare..."
        )
    zone = zones[0]
    zone_id = zone["id"]
    logger.debug(f"{zone_id}: {zone=}")

    # purge_files = [f"https://{base_hostname}{p}" for p in purge_paths]
    # logger.debug(
    #     f"Sending purge_cache request for {zone_id=} at prefixes: {purge_files=}"
    # )
    purge_data = {
        "purge_everything": True,
    }
    logger.debug(f"Sending purge_cache request for {zone_id=} with {purge_data=}")
    purge_response = cf.zones.purge_cache.post(
        zone["id"],
        data=purge_data,
    )
    logger.debug(f"{purge_response=}")
    return purge_response


def prime_cache(site_hostname, new_paths):
    responses = []
    for new_path in new_paths:
        response = requests.get(
            url=f"https://{site_hostname}{new_path}",
        )
        logger.debug(f"{response=}")
        logger.debug(f"{response.headers=}")
        response.raise_for_status()
        responses.append(response)
    return responses


def build_static_site(site_hostname, cloudflare_zone, purge_delay_secs=30):
    freeze_result = freeze_site(app=create_app())
    storage.upload_build_to_gcs(
        client=storage.get_client(),
        bucket_id=site_hostname,
    )
    if cloudflare_zone is not None:
        purge_cache(
            CloudFlare(token=get_cloudflare_api_token()),
            cloudflare_zone=cloudflare_zone,
        )
        logger.info(f"Waiting for {purge_delay_secs=} before proceeding...")
        sleep(purge_delay_secs)
    else:
        logger.warning(f"Skipping cache purge bits as {cloudflare_zone}")
    prime_cache(site_hostname=site_hostname, new_paths=freeze_result)


if __name__ == "__main__":
    import argparse
    import logging

    import logzero

    cfg.load()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-q",
        "--quiet",
        help="modify output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "-s",
        "--site-hostname",
        default=cfg.hostname,
        help="Fully-qualified domain name of the published site. Used in cache purging / priming methods.",
    )
    parser.add_argument(
        "-z",
        "--cloudflare-zone",
        default=cfg.get("cloudflare_zone"),
        help="Name of zone at CDN provider (Cloudflare only provider currently considered / supported).",
    )
    args = parser.parse_args()

    if args.quiet:
        logzero.loglevel(logging.INFO)

    build_static_site(
        site_hostname=args.site_hostname,
        cloudflare_zone=args.cloudflare_zone,
    )
