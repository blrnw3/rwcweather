import json
import os
from json import JSONDecodeError

import click
import requests

from rwcwx import logger
from rwcwx.config import AQI_FILE_NAME


class ExternalDataGrabber:
    """
    Get and save external weather data
    """

    PURPLE_AIR_URI = "https://api.purpleair.com/v1/sensors/65517"
    API_KEY = os.getenv("PA_API_KEY")
    ALT_STATION_URI = ""

    def __init__(self, out_dir: str) -> None:
        self.out_dir = out_dir

    def run(self) -> None:
        try:
            self.get_aqi()
        except JSONDecodeError as e:
            logger.exception("Failed decoding reponse", exc_info=e)

    def get_aqi(self) -> None:
        # NB: https://github.com/hrbonz/python-aqi
        logger.info(f"Getting aqi data from {self.PURPLE_AIR_URI}")

        try:
            resp = requests.get(url=self.PURPLE_AIR_URI, headers={"X-API-Key": self.API_KEY})
        except OSError as e:
            logger.exception("Could not hit purple air.", exc_info=e)
            return

        save_location = os.path.join(self.out_dir, AQI_FILE_NAME)
        logger.info(f"Saving aqi data to {save_location}")
        with open(save_location, "w") as f:
            json.dump(resp.json(), f)
        logger.info("Saved ok")


@click.command()
@click.option("-o", "--out-dir", required=True)
def main(out_dir: str) -> None:
    external_grabber = ExternalDataGrabber(out_dir)
    external_grabber.run()


if __name__ == "__main__":
    main()
