import json
import os

import click
import requests

from rwcwx import logger
from rwcwx.config import AQI_FILE_NAME


class ExternalDataGrabber:
    """
    Get and save external weather data
    """

    PURPLE_AIR_URI = "https://www.purpleair.com/json?key=XZAC8NRA6BSXDNDO&show=65141"

    def __init__(self, out_dir: str) -> None:
        self.out_dir = out_dir

    def run(self) -> None:
        self.get_aqi()

    def get_aqi(self) -> None:
        # NB: https://github.com/hrbonz/python-aqi
        logger.info(f"Getting aqi data from {self.PURPLE_AIR_URI}")
        resp = requests.get(url=self.PURPLE_AIR_URI)
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
